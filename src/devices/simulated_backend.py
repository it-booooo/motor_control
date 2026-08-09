"""Backend with no hardware, used for UI and backend-contract testing."""

from dataclasses import replace
import time

from ..models import CanStatistics, MotorCommand, MotorStateSnapshot, MotorTelemetry, TimestampSet
from ..motors import ControlMode, MotorProfile
from .motor_backend import BackendType, MotorBackend


class SimulatedMotorBackend(MotorBackend):
    backend_type = BackendType.SIMULATION

    def __init__(
        self,
        profile: MotorProfile,
        control_mode: ControlMode = ControlMode.MIT,
    ):
        super().__init__(profile, control_mode)
        self._open = False
        self._position = 0.0
        self._last_t = None
        self._last_command = MotorCommand.idle(control_mode)
        self._sequence = 0

    @property
    def last_command(self) -> MotorCommand:
        return self._last_command

    def open(self) -> None:
        self._open = True
        self._last_t = time.perf_counter()

    def close(self) -> None:
        self._open = False

    def command(self, command: MotorCommand) -> MotorCommand:
        if command.mode is not self.control_mode:
            raise ValueError("Simulation command mode does not match backend mode")
        command.validate()
        self._sequence += 1
        self._last_command = command.stamped(self._sequence)
        return self._last_command

    def idle(self) -> None:
        self.command(MotorCommand.idle(self.control_mode))

    def read_telemetry(self) -> MotorTelemetry | None:
        if not self._open:
            return None
        now = time.perf_counter()
        dt = max(0.0, now - self._last_t)
        self._last_t = now
        velocity = self._last_command.velocity_rads
        self._position += velocity * dt
        current = self._last_command.torque_nm
        host_rx_ns = time.perf_counter_ns()
        return MotorTelemetry(
            sequence=self._sequence,
            timestamps=TimestampSet(
                t_host_command_ns=self._last_command.t_host_command_ns,
                t_host_rx_ns=host_rx_ns,
            ),
            position_rad=self._position,
            velocity_rads=velocity,
            current_a=current,
            temperature_c=25.0,
            motor_error=0,
            can_statistics=CanStatistics(
                can_tx_count=self._sequence,
                can_rx_count=self._sequence,
                can_tx_error=0,
                can_rx_error=0,
                bus_off_count=0,
            ),
        )

    def read_state(self):
        telemetry = self.read_telemetry()
        if telemetry is None:
            return None
        return replace(
            MotorStateSnapshot.from_telemetry(telemetry), age_can_s=0.0
        )

    def get_can_statistics(self) -> CanStatistics:
        telemetry = self.read_telemetry()
        return telemetry.can_statistics if telemetry else CanStatistics()
