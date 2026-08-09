"""Primary backend: Python exchanges application packets with STM32."""

import threading
import time

from ..communication import BackendConfiguration, Heartbeat, SerialSTM32Transport
from ..models import CanStatistics, MotorCommand, MotorStateSnapshot, MotorTelemetry, SafetyLimits
from ..motors import ControlMode, MotorProfile
from .motor_backend import BackendType, MotorBackend


class STM32MotorBackend(MotorBackend):
    """Laboratory backend that sends high-level packets to STM32 firmware.

    Python owns USB/serial transport, latest-telemetry access and worker-facing
    commands.  STM32 owns realtime CAN scheduling, electrical CAN interfacing,
    MIT payload execution and sensor sampling timing.
    """
    backend_type = BackendType.STM32

    def __init__(
        self,
        profile: MotorProfile,
        *,
        motor_id: int,
        port: str,
        baud: int,
        can_bitrate: int,
        command_rate_hz: int,
        safety: SafetyLimits,
        control_mode: ControlMode = ControlMode.MIT,
        transport=None,
        heartbeat_hz: float = 10.0,
    ):
        super().__init__(profile, control_mode)
        profile.require_hardware_parameters(control_mode)
        self.motor_id = motor_id
        self.can_bitrate = can_bitrate
        self.command_rate_hz = command_rate_hz
        self.safety = safety
        self.transport = transport or SerialSTM32Transport(port, baud)
        self.heartbeat_hz = heartbeat_hz
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        self._last_command_sequence = None
        self._running = False
        self._telemetry = None
        self._telemetry_lock = threading.Lock()
        # RX and experiment threads access this reference concurrently.  Lock
        # replacement/read so a consumer always receives one complete sample.
        self._send_lock = threading.Lock()
        self._rx_thread = None
        self._heartbeat_thread = None
        self.last_transport_error = None

    def _next_sequence(self) -> int:
        with self._sequence_lock:
            self._sequence = (self._sequence + 1) & 0xFFFFFFFF
            return self._sequence

    def _send(self, packet) -> None:
        """Serialize application-packet writes from commands and heartbeat."""
        with self._send_lock:
            self.transport.send_command(packet)

    def open(self) -> None:
        """Configure STM32 then start non-GUI receive and watchdog threads."""
        if self._running:
            return
        self.safety.validate()
        self.transport.open()
        self._send(
            BackendConfiguration(
                sequence=self._next_sequence(),
                motor_id=self.motor_id,
                control_mode=self.control_mode,
                motor_profile_key=self.profile.key,
                can_bitrate=self.can_bitrate,
                command_rate_hz=self.command_rate_hz,
                safety=self.safety,
            )
        )
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._rx_thread.start()
        self._heartbeat_thread.start()

    def close(self) -> None:
        """Request idle before closing transport; bounded joins avoid UI hangs."""
        if not self._running:
            self.transport.close()
            return
        try:
            self.idle()
        finally:
            self._running = False
            for thread in (self._rx_thread, self._heartbeat_thread):
                if thread is not None:
                    thread.join(timeout=0.5)
            self.transport.close()

    def command(self, command: MotorCommand) -> MotorCommand:
        if command.mode is not self.control_mode:
            raise ValueError(
                f"Command mode {command.mode.value} does not match backend mode "
                f"{self.control_mode.value}"
            )
        command.validate()
        stamped = command.stamped(self._next_sequence())
        self._send(stamped)
        self._last_command_sequence = stamped.sequence
        return stamped

    def idle(self) -> None:
        self.command(MotorCommand.idle(self.control_mode))

    def _rx_loop(self) -> None:
        """Store the latest complete telemetry packet received by the RX thread."""
        while self._running:
            try:
                packet = self.transport.read_packet(timeout=0.1)
            except Exception as exc:
                self.last_transport_error = str(exc)
                self._running = False
                break
            if isinstance(packet, MotorTelemetry):
                with self._telemetry_lock:
                    self._telemetry = packet

    def _heartbeat_loop(self) -> None:
        """Keep STM32's host watchdog alive using a monotonic host timestamp."""
        period = 1.0 / max(self.heartbeat_hz, 0.1)
        while self._running:
            try:
                self._send(
                    Heartbeat(
                        sequence=self._next_sequence(),
                        t_host_ns=time.perf_counter_ns(),
                        last_command_sequence=self._last_command_sequence,
                    )
                )
            except Exception as exc:
                self.last_transport_error = str(exc)
                self._running = False
                break
            time.sleep(period)

    def read_telemetry(self) -> MotorTelemetry | None:
        """Return the latest complete sample, or ``None`` before first feedback."""
        with self._telemetry_lock:
            return self._telemetry

    def read_state(self):
        telemetry = self.read_telemetry()
        return (
            MotorStateSnapshot.from_telemetry(telemetry)
            if telemetry is not None
            else None
        )

    def get_can_statistics(self) -> CanStatistics:
        telemetry = self.read_telemetry()
        return telemetry.can_statistics if telemetry is not None else CanStatistics()
