"""Backend-neutral command and safety models."""

from dataclasses import dataclass, replace
import math
import time

from ..motors.control_modes import ControlMode


@dataclass(frozen=True)
class SafetyLimits:
    """Software limits supplied to the backend and STM32 watchdog policy.

    These limits reduce sustained overload risk; they do not replace the
    physical E-stop, fuse, fixture limits, or power cutoff.
    """
    torque_nm: float
    current_a: float
    temperature_c: float

    def validate(self) -> None:
        for name, value in (
            ("torque", self.torque_nm),
            ("current", self.current_a),
            ("temperature", self.temperature_c),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Safety {name} limit must be a positive finite value")


@dataclass(frozen=True)
class MotorCommand:
    """Backend-neutral command expressed in output-shaft SI units.

    The sequence and host timestamp are added at the backend boundary so a
    command's identity reflects submission to transport, not UI interaction.
    """
    sequence: int
    mode: ControlMode
    position_rad: float = 0.0
    velocity_rads: float = 0.0
    kp: float = 0.0
    kd: float = 0.0
    torque_nm: float = 0.0
    t_host_command_ns: int | None = None

    def stamped(self, sequence: int) -> "MotorCommand":
        """Assign transport sequence and a monotonic host submission timestamp."""
        return replace(
            self,
            sequence=sequence,
            t_host_command_ns=time.perf_counter_ns(),
        )

    def validate(self) -> None:
        values = (
            self.position_rad,
            self.velocity_rads,
            self.kp,
            self.kd,
            self.torque_nm,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Motor command fields must be finite")

    @classmethod
    def idle(cls, mode: ControlMode = ControlMode.MIT) -> "MotorCommand":
        return cls(sequence=0, mode=mode)

    @classmethod
    def torque_through_mit(cls, torque_nm: float) -> "MotorCommand":
        """Request torque through MIT Control Mode with ``kp = kd = 0``.

        This is feed-forward torque inside an MIT command, not necessarily the
        actuator's independent native Torque Control Mode.
        """

        return cls(sequence=0, mode=ControlMode.MIT, torque_nm=torque_nm)

    @classmethod
    def velocity_through_mit(
        cls, velocity_rads: float, kd: float = 2.0
    ) -> "MotorCommand":
        """Velocity command through MIT Control Mode, not native Velocity Mode."""

        return cls(
            sequence=0,
            mode=ControlMode.MIT,
            velocity_rads=velocity_rads,
            kd=kd,
        )
