"""Shared experiment metadata and validation, independent of the GUI."""

EXPERIMENT_LABELS = {
    "verify": "0. 縮放常數驗證",
    "kt": "1. 扭力常數校正",
    "asym": "2. 正反向不對稱",
    "backdrive": "3. 反驅阻力",
    "thermal": "4. 熱衰減",
}

EXPERIMENT_HELP = {
    "verify": "先用手轉動輸出軸約 90°，再拆除力臂進行低速旋轉，以位置微分交叉驗證速度換算。",
    "kt": "正扭力階梯掃描；每階量測後回到 idle 休息，用於 Kt、指令準確度與飽和點分析。",
    "asym": "正負扭力交錯掃描，降低溫度漂移造成的偏差，用於比較抬升與下壓方向。",
    "backdrive": "馬達保持 idle，由手緩慢來回推動力臂，量測庫倫摩擦與黏滯阻尼。",
    "thermal": "固定扭力長時間輸出並記錄升溫、扭力衰減及降溫曲線。",
}


def estimated_duration(kind, params):
    if kind == "verify":
        return float(params["spin_duration_s"]) + 2.0
    if kind == "kt":
        return 2.0 + int(params["steps"]) * (
            float(params["hold_s"]) + float(params["rest_s"])
        )
    if kind == "asym":
        return 2 * int(params["steps"]) * (
            float(params["hold_s"]) + float(params["rest_s"])
        )
    if kind == "backdrive":
        return float(params["duration_s"])
    if kind == "thermal":
        return 10.0 + float(params["duration_s"]) + float(params["cooldown_s"])
    raise ValueError(f"未知實驗：{kind}")


def validate_request(kind, params, hardware):
    if kind not in EXPERIMENT_LABELS:
        raise ValueError(f"未知實驗：{kind}")
    if hardware["safe_torque_max"] <= 0:
        raise ValueError("安全扭力上限必須大於 0")
    if hardware["lever_m"] <= 0:
        raise ValueError("力臂長度必須大於 0")
    if not hardware.get("can_interface") or not hardware.get("can_channel"):
        raise ValueError("CAN 介面與通道不可空白")
    if kind != "verify" and not hardware.get("loadcell_port"):
        raise ValueError("此實驗需要設定 load cell 序列埠")
    requested = 0.0
    if kind in {"kt", "asym"}:
        requested = float(params["torque_max"])
    elif kind == "thermal":
        requested = abs(float(params["torque"]))
    if requested > float(hardware["safe_torque_max"]):
        raise ValueError(
            f"實驗扭力 {requested:.2f} N·m 超過軟體安全上限 "
            f"{hardware['safe_torque_max']:.2f} N·m"
        )
    if estimated_duration(kind, params) <= 0:
        raise ValueError("實驗時間必須大於 0")
