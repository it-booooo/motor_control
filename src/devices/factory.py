from ..models import SafetyLimits
from ..motors import ControlMode, get_motor_profile
from .motor_backend import BackendType


def create_motor_backend(settings):
    backend = BackendType(settings.get("backend", BackendType.DIRECT_CAN.value))
    profile = get_motor_profile(settings.get("motor_profile", "ak10-9-v3-kv60"))
    control_mode = ControlMode(settings.get("control_mode", ControlMode.MIT.value))
    if backend is BackendType.SIMULATION:
        from .simulated_backend import SimulatedMotorBackend

        return SimulatedMotorBackend(profile, control_mode)
    profile.require_hardware_parameters(control_mode)
    if backend is BackendType.DIRECT_CAN:
        from .direct_can_backend import DirectCANMotorBackend

        return DirectCANMotorBackend(
            profile,
            motor_id=settings["motor_id"],
            interface=settings["can_interface"],
            channel=settings["can_channel"],
            bitrate=settings["can_bitrate"],
            command_rate_hz=settings["command_rate_hz"],
            control_mode=control_mode,
        )
    from .stm32_backend import STM32MotorBackend

    return STM32MotorBackend(
        profile,
        motor_id=settings["motor_id"],
        port=settings["stm32_port"],
        baud=settings["stm32_baud"],
        can_bitrate=settings["can_bitrate"],
        command_rate_hz=settings["command_rate_hz"],
        safety=SafetyLimits(
            torque_nm=settings["safe_torque_max"],
            current_a=settings["safe_current_a"],
            temperature_c=settings["safe_temp_c"],
        ),
        control_mode=control_mode,
    )
