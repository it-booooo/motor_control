from dataclasses import dataclass, field
import config

from .runtime import application_root


@dataclass
class HardwareSettings:
    can_interface: str = config.CAN_INTERFACE
    can_channel: str = config.CAN_CHANNEL
    can_bitrate: int = config.CAN_BITRATE
    motor_id: int = config.MOTOR_ID
    command_rate_hz: int = config.CMD_RATE_HZ
    loadcell_port: str = config.LOADCELL_PORT
    loadcell_baud: int = config.LOADCELL_BAUD
    loadcell_sign: float = config.LOADCELL_SIGN
    lever_m: float = config.LEVER_ARM_M
    safe_torque_max: float = config.SAFE_TORQUE_MAX
    safe_current_a: float = config.SAFE_CURRENT_A
    safe_temp_c: float = config.SAFE_TEMP_C
    log_rate_hz: int = config.LOG_RATE_HZ
    log_dir: str = str((application_root() / config.LOG_DIR).resolve())


@dataclass
class AppState:
    hardware: HardwareSettings = field(default_factory=HardwareSettings)
    last_data_path: str = ""
