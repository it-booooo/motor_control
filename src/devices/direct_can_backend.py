"""Legacy/debug backend: Python talks directly to the actuator through USB-CAN."""

from ak_can import AKMotor

from ..models import CanStatistics, MotorCommand
from ..motors import ControlMode, MotorProfile
from .motor_backend import BackendType, MotorBackend


class DirectCANMotorBackend(MotorBackend):
    backend_type = BackendType.DIRECT_CAN

    def __init__(
        self,
        profile: MotorProfile,
        *,
        motor_id: int,
        interface: str,
        channel: str,
        bitrate: int,
        command_rate_hz: float,
        control_mode: ControlMode = ControlMode.MIT,
        motor=None,
    ):
        super().__init__(profile, control_mode)
        profile.require_hardware_parameters(control_mode)
        if profile.key != "ak10-9-v3-kv60":
            raise ValueError(
                "Legacy Direct CAN codec is verified only for the AK10-9 profile"
            )
        if control_mode is not ControlMode.MIT:
            raise ValueError("Legacy Direct CAN currently implements MIT Control Mode only")
        self._motor = motor or AKMotor(
            motor_id=motor_id,
            interface=interface,
            channel=channel,
            bitrate=bitrate,
            command_rate_hz=command_rate_hz,
        )

    def open(self) -> None:
        self._motor.open()

    def close(self) -> None:
        self._motor.close()

    def command(self, command: MotorCommand) -> MotorCommand:
        if command.mode is not ControlMode.MIT:
            raise ValueError("Direct CAN command is not in MIT Control Mode")
        command.validate()
        self._motor.set_command(
            command.position_rad,
            command.velocity_rads,
            command.kp,
            command.kd,
            command.torque_nm,
        )
        return command

    def read_state(self):
        return self._motor.read()

    def idle(self) -> None:
        self._motor.idle()

    def get_can_statistics(self) -> CanStatistics:
        getter = getattr(self._motor, "get_can_statistics", None)
        return getter() if getter is not None else CanStatistics()
