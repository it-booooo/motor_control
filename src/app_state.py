from dataclasses import dataclass, field
import config

@dataclass
class HardwareSettings:
    backend: str = config.HARDWARE_BACKEND
    motor_profile: str = config.MOTOR_PROFILE
    control_mode: str = config.CONTROL_MODE
    stm32_port: str = config.STM32_PORT
    stm32_baud: int = config.STM32_BAUD
    can_interface: str = config.CAN_INTERFACE
    can_channel: str = config.CAN_CHANNEL
    can_bitrate: int = config.CAN_BITRATE
    motor_id: int = config.MOTOR_ID
    command_rate_hz: int = config.CMD_RATE_HZ
    safe_torque_max: float = config.SAFE_TORQUE_MAX
    safe_current_a: float = config.SAFE_CURRENT_A
    safe_temp_c: float = config.SAFE_TEMP_C


@dataclass
class AppState:
    hardware: HardwareSettings = field(default_factory=HardwareSettings)
    last_data_path: str = ""
