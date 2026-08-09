"""CAN payload codec for commands sent while the actuator is in MIT Control Mode.

MIT is a control mode.  This module only encodes/decodes that mode's CAN data
field; it does not define PC-to-STM32 transport or call a CAN driver.
"""

from dataclasses import dataclass

from .profiles import AK10_9_V3_KV60, MotorProfile


def float_to_uint(value: float, minimum: float, maximum: float, bits: int) -> int:
    span = maximum - minimum
    value = min(max(value, minimum), maximum)
    return int(round((value - minimum) * ((2**bits - 1) / span)))


def uint_to_float(value: int, minimum: float, maximum: float, bits: int) -> float:
    return value * (maximum - minimum) / (2**bits - 1) + minimum


@dataclass(frozen=True)
class MITCommandFields:
    position_rad: float
    velocity_rads: float
    kp: float
    kd: float
    torque_nm: float


def _limits(profile: MotorProfile) -> tuple[float, ...]:
    missing = profile.missing_mit_codec_fields()
    if missing:
        raise ValueError(
            f"{profile.display_name} MIT Control Mode codec is incomplete: "
            + ", ".join(missing)
        )
    return (
        profile.p_min, profile.p_max, profile.v_min, profile.v_max,
        profile.t_min, profile.t_max, profile.kp_min, profile.kp_max,
        profile.kd_min, profile.kd_max,
    )


def encode_mit_command(
    position_rad: float,
    velocity_rads: float,
    kp: float,
    kd: float,
    torque_nm: float,
    *,
    profile: MotorProfile = AK10_9_V3_KV60,
) -> bytes:
    p_min, p_max, v_min, v_max, t_min, t_max, kp_min, kp_max, kd_min, kd_max = _limits(profile)
    p_int = float_to_uint(position_rad, p_min, p_max, 16)
    v_int = float_to_uint(velocity_rads, v_min, v_max, 12)
    kp_int = float_to_uint(kp, kp_min, kp_max, 12)
    kd_int = float_to_uint(kd, kd_min, kd_max, 12)
    t_int = float_to_uint(torque_nm, t_min, t_max, 12)
    return bytes(
        [
            (kp_int >> 4) & 0xFF,
            ((kp_int & 0x0F) << 4) | ((kd_int >> 8) & 0x0F),
            kd_int & 0xFF,
            (p_int >> 8) & 0xFF,
            p_int & 0xFF,
            (v_int >> 4) & 0xFF,
            ((v_int & 0x0F) << 4) | ((t_int >> 8) & 0x0F),
            t_int & 0xFF,
        ]
    )


def decode_mit_command(
    data: bytes, *, profile: MotorProfile = AK10_9_V3_KV60
) -> MITCommandFields:
    if len(data) != 8:
        raise ValueError("MIT Control Mode command must contain exactly 8 bytes")
    p_min, p_max, v_min, v_max, t_min, t_max, kp_min, kp_max, kd_min, kd_max = _limits(profile)
    kp_int = (data[0] << 4) | (data[1] >> 4)
    kd_int = ((data[1] & 0x0F) << 8) | data[2]
    p_int = (data[3] << 8) | data[4]
    v_int = (data[5] << 4) | (data[6] >> 4)
    t_int = ((data[6] & 0x0F) << 8) | data[7]
    return MITCommandFields(
        position_rad=uint_to_float(p_int, p_min, p_max, 16),
        velocity_rads=uint_to_float(v_int, v_min, v_max, 12),
        kp=uint_to_float(kp_int, kp_min, kp_max, 12),
        kd=uint_to_float(kd_int, kd_min, kd_max, 12),
        torque_nm=uint_to_float(t_int, t_min, t_max, 12),
    )
