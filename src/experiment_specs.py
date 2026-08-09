"""Validation for motor-only communication and feedback checks."""

from .motors import ControlMode, get_motor_profile


EXPERIMENT_LABELS = {"verify": "Motor Feedback / Scaling Check"}
EXPERIMENT_HELP = {
    "verify": (
        "只使用 motor command 與 motor feedback：檢查位置回授，並以低速命令"
        "交叉確認速度換算與馬達回授。"
    )
}


def estimated_duration(kind, params):
    if kind == "verify":
        return float(params["spin_duration_s"]) + 2.0
    raise ValueError(f"未知實驗：{kind}")


def validate_hardware_settings(hardware):
    for key, label in (
        ("safe_torque_max", "安全扭力"),
        ("safe_current_a", "安全電流"),
        ("safe_temp_c", "安全溫度"),
    ):
        if float(hardware[key]) <= 0:
            raise ValueError(f"{label}上限必須大於 0")
    backend = hardware.get("backend", "direct_can")
    if backend not in {"stm32", "direct_can", "simulation"}:
        raise ValueError(f"未知 Hardware Backend：{backend}")
    if backend == "stm32" and not hardware.get("stm32_port"):
        raise ValueError("STM32 backend 必須設定 STM32 Port")
    if backend == "direct_can" and (
        not hardware.get("can_interface") or not hardware.get("can_channel")
    ):
        raise ValueError("Direct CAN backend 的 CAN 介面與通道不可空白")
    if int(hardware.get("command_rate_hz", 1)) <= 0:
        raise ValueError("CAN command rate 必須大於 0")

    profile = get_motor_profile(
        hardware.get("motor_profile", "ak10-9-v3-kv60")
    )
    raw_mode = hardware.get("control_mode", ControlMode.MIT.value)
    if not raw_mode:
        raise ValueError(f"{profile.display_name} 尚無已確認的控制模式")
    mode = ControlMode(raw_mode)
    if backend != "simulation":
        profile.require_hardware_parameters(mode)


def validate_request(kind, params, hardware):
    if kind != "verify":
        raise ValueError(f"未知實驗：{kind}")
    validate_hardware_settings(hardware)
    if float(params["spin_duration_s"]) <= 0:
        raise ValueError("取樣時間必須大於 0")
    if float(params["velocity_rads"]) == 0:
        raise ValueError("測試速度不可為 0")
