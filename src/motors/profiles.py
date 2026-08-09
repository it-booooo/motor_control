"""Motor-specific limits and capabilities.

Unknown values intentionally remain ``None``.  A profile with missing codec
parameters cannot be selected for a real hardware backend.
"""

from dataclasses import dataclass

from .control_modes import CommunicationType, ControlMode


@dataclass(frozen=True)
class MotorProfile:
    """Immutable actuator facts used to validate a selected hardware path.

    This model owns profile-specific limits and CAN codec ranges; it does not
    infer missing values from a similar motor.  ``None`` means the lab has not
    verified the value from the exact actuator/firmware combination, so a real
    backend must refuse any mode that depends on it.
    """
    key: str
    display_name: str
    communication: CommunicationType
    supported_control_modes: tuple[ControlMode, ...]
    gear_ratio: float | None
    pole_pairs: int | None
    p_min: float | None
    p_max: float | None
    v_min: float | None
    v_max: float | None
    t_min: float | None
    t_max: float | None
    rated_torque: float | None
    peak_torque: float | None
    safe_current_a: float | None
    safe_temp_c: float | None
    kp_min: float | None = None
    kp_max: float | None = None
    kd_min: float | None = None
    kd_max: float | None = None
    mit_mode_can_id: int | None = None
    notes: str = ""

    def missing_mit_codec_fields(self) -> tuple[str, ...]:
        names = (
            "p_min", "p_max", "v_min", "v_max", "t_min", "t_max",
            "kp_min", "kp_max", "kd_min", "kd_max", "mit_mode_can_id",
        )
        return tuple(name for name in names if getattr(self, name) is None)

    def require_hardware_parameters(self, mode: ControlMode) -> None:
        if mode not in self.supported_control_modes:
            raise ValueError(
                f"{self.display_name} 尚未確認支援 {mode.value} control mode"
            )
        if mode is ControlMode.MIT:
            missing = self.missing_mit_codec_fields()
            if missing:
                raise ValueError(
                    f"{self.display_name} 缺少正式硬體測試所需參數："
                    + ", ".join(missing)
                )


# ASSUMPTION: These values preserve the existing AK10-9 implementation.
# Velocity, torque and pole-pair scaling still need physical verification; do
# not reuse them for another actuator merely because its CAN payload is similar.
AK10_9_V3_KV60 = MotorProfile(
    key="ak10-9-v3-kv60",
    display_name="AK10-9 V3.0 KV60",
    communication=CommunicationType.CAN,
    supported_control_modes=(ControlMode.MIT,),
    gear_ratio=9.0,  # SPEC: nominal output-shaft gearbox ratio.
    pole_pairs=21,  # TODO(AK10-9): verify against the installed firmware/manual.
    p_min=-12.56,
    p_max=12.56,
    v_min=-33.0,
    v_max=33.0,
    t_min=-65.0,
    t_max=65.0,
    rated_torque=None,
    peak_torque=None,
    safe_current_a=25.0,
    safe_temp_c=70.0,
    kp_min=0.0,
    kp_max=500.0,
    kd_min=0.0,
    kd_max=5.0,
    mit_mode_can_id=0x08,
    notes=(
        "Existing project values. V/T scaling and pole pairs still require "
        "the documented physical verification."
    ),
)


# Only the identity is registered.  Official scaling, CAN-frame layout and
# parameter ranges are unknown, so this profile deliberately cannot enable CAN.
AK70_10_KV100 = MotorProfile(
    key="ak70-10-kv100",
    display_name="AK70-10 KV100",
    communication=CommunicationType.CAN,
    supported_control_modes=(),
    gear_ratio=None,
    pole_pairs=None,
    p_min=None,
    p_max=None,
    v_min=None,
    v_max=None,
    t_min=None,
    t_max=None,
    rated_torque=None,
    peak_torque=None,
    safe_current_a=None,
    safe_temp_c=None,
    notes="TODO: populate only from the exact official motor/firmware manual.",
)


MOTOR_PROFILES = {
    profile.key: profile for profile in (AK10_9_V3_KV60, AK70_10_KV100)
}


def get_motor_profile(key: str) -> MotorProfile:
    """Return the named profile without guessing an actuator configuration.

    Args:
        key: Stable profile identifier stored in the application settings.

    Raises:
        KeyError: If no explicitly registered profile has this identifier.
    """
    try:
        return MOTOR_PROFILES[key]
    except KeyError as exc:
        raise KeyError(f"Unknown motor profile: {key}") from exc
