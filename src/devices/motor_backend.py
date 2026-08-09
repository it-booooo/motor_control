"""Backend boundary seen by controllers, workers and experiments."""

from abc import ABC, abstractmethod
from enum import Enum

from ..models import CanStatistics, MotorCommand, MotorTelemetry
from ..motors import CommunicationType, ControlMode, MotorProfile


class BackendType(str, Enum):
    STM32 = "stm32"
    DIRECT_CAN = "direct_can"
    SIMULATION = "simulation"


class MotorBackend(ABC):
    """Interface used by experiment workers, independent of physical wiring.

    Implementations own connection lifecycle and conversion to normalized
    telemetry.  They do not own UI state or realtime actuator scheduling; for
    the STM32 backend, the latter belongs to firmware.
    """
    communication = CommunicationType.CAN
    backend_type: BackendType

    def __init__(self, profile: MotorProfile, control_mode: ControlMode):
        self.profile = profile
        self.control_mode = control_mode

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def command(self, command: MotorCommand) -> MotorCommand:
        raise NotImplementedError

    @abstractmethod
    def read_state(self):
        raise NotImplementedError

    @abstractmethod
    def idle(self) -> None:
        raise NotImplementedError

    def read(self):
        """Compatibility alias for the existing experiment/recorder code."""

        return self.read_state()

    def read_telemetry(self) -> MotorTelemetry | None:
        return None

    def get_can_statistics(self) -> CanStatistics:
        return CanStatistics()

    def set_command(self, p_des=0.0, v_des=0.0, kp=0.0, kd=0.0, t_ff=0.0):
        self.command(
            MotorCommand(
                sequence=0,
                mode=self.control_mode,
                position_rad=p_des,
                velocity_rads=v_des,
                kp=kp,
                kd=kd,
                torque_nm=t_ff,
            )
        )

    def torque(self, torque_nm: float) -> None:
        """Request MIT feed-forward torque [N*m] with ``kp = kd = 0``.

        This helper intentionally rejects non-MIT backends to avoid labelling a
        protocol-specific command as an actuator-native torque control mode.
        """

        if self.control_mode is not ControlMode.MIT:
            raise RuntimeError("Torque-through-MIT requires MIT Control Mode")
        self.command(MotorCommand.torque_through_mit(torque_nm))

    def velocity(self, velocity_rads: float, kd: float = 2.0) -> None:
        """Request velocity [rad/s] through MIT Control Mode, not native mode."""

        if self.control_mode is not ControlMode.MIT:
            raise RuntimeError("Velocity-through-MIT requires MIT Control Mode")
        self.command(MotorCommand.velocity_through_mit(velocity_rads, kd))

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_exc):
        self.close()
