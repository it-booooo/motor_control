import queue
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal

from ..devices import create_motor_backend
from ..models import MotorCommand
from ..motors import ControlMode


class ManualControlWorker(QThread):
    status = Signal(str)
    telemetry = Signal(dict)
    connected = Signal(bool, str)
    completed = Signal(str)

    def __init__(self, hardware, parent=None):
        super().__init__(parent)
        self.hardware = hardware
        self._stop = threading.Event()
        self._commands = queue.Queue()
        self._motor = None

    def request_command(self, values):
        self._commands.put(("command", dict(values)))

    def request_idle(self):
        self._commands.put(("idle", None))

    def request_stop(self):
        self._stop.set()

    def _build_command(self, values):
        intent = values["intent"]
        if intent == "torque_mit":
            return MotorCommand.torque_through_mit(values["torque_nm"])
        if intent == "velocity_mit":
            return MotorCommand.velocity_through_mit(
                values["velocity_rads"], values["kd"]
            )
        if intent == "position_mit":
            return MotorCommand(
                sequence=0,
                mode=ControlMode.MIT,
                position_rad=values["position_rad"],
                kp=values["kp"],
                kd=values["kd"],
            )
        return MotorCommand(
            sequence=0,
            mode=ControlMode.MIT,
            position_rad=values["position_rad"],
            velocity_rads=values["velocity_rads"],
            kp=values["kp"],
            kd=values["kd"],
            torque_nm=values["torque_nm"],
        )

    def _safety_check(self, state):
        if state.error:
            raise RuntimeError(f"Motor error: {state.error}")
        if abs(state.current_a) > self.hardware["safe_current_a"]:
            raise RuntimeError("Current limit exceeded")
        if state.temp_c > self.hardware["safe_temp_c"]:
            raise RuntimeError("Temperature limit exceeded")

    def run(self):
        message = "Manual control disconnected"
        try:
            self._motor = create_motor_backend(self.hardware)
            self._motor.open()
            deadline = time.perf_counter() + 3.0
            while not self._stop.is_set() and self._motor.read() is None:
                if time.perf_counter() >= deadline:
                    raise RuntimeError("Backend opened but no motor telemetry was received")
                time.sleep(0.03)
            self.connected.emit(True, "Manual control backend connected")
            while not self._stop.is_set():
                try:
                    action, payload = self._commands.get(timeout=0.03)
                    if action == "idle":
                        self._motor.idle()
                        self.status.emit("Motor Idle command sent")
                    else:
                        command = self._build_command(payload)
                        if abs(command.torque_nm) > self.hardware["safe_torque_max"]:
                            raise RuntimeError("Manual torque exceeds software safety limit")
                        self._motor.command(command)
                        self.status.emit("Logical command sent through backend")
                except queue.Empty:
                    pass
                state = self._motor.read()
                if state is not None:
                    self._safety_check(state)
                    values = {
                        "phase": "manual",
                        "backend": self._motor.backend_type.value,
                        "position": state.pos_deg,
                        "speed": state.spd_rads,
                        "current": state.current_a,
                        "temperature": state.temp_c,
                    }
                    statistics = self._motor.get_can_statistics()
                    values.update(
                        can_tx=statistics.can_tx_count,
                        can_rx=statistics.can_rx_count,
                        can_errors=(statistics.can_tx_error or 0)
                        + (statistics.can_rx_error or 0)
                        if statistics.can_tx_error is not None
                        or statistics.can_rx_error is not None
                        else None,
                    )
                    self.telemetry.emit(values)
        except Exception as exc:
            message = f"Manual control stopped: {exc}"
            self.status.emit(message)
            self.status.emit(traceback.format_exc())
        finally:
            if self._motor is not None:
                try:
                    self._motor.idle()
                except Exception:
                    pass
                try:
                    self._motor.close()
                except Exception:
                    pass
            self._motor = None
            self.connected.emit(False, message)
            self.completed.emit(message)
