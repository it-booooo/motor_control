"""
experiments.py — 五組實驗

執行方式：
    python experiments.py verify      # 0. 縮放常數驗證（★ 一定要先做這個）
    python experiments.py kt          # 1. 扭力常數校正掃描
    python experiments.py asym        # 2. 正反向不對稱（抬 vs 頂）
    python experiments.py backdrive   # 3. 可反向驅動阻力
    python experiments.py thermal     # 4. 熱衰減

★★★ 開始前務必確認 ★★★
  1. 馬達底座鎖死在桌面/工作台上（不是只放著，AK10-9 峰值扭力 53 N·m 會把桌上的東西掃飛）
  2. 力臂兩側有機械限位，防止失控時全速旋轉
  3. 電源供應器的實體開關在你伸手可及的地方，這是你的 E-stop
  4. 第一次跑把 config.SAFE_TORQUE_MAX 設到 3 N·m，確認一切正常再往上調
"""

import math
import sys
import time

from ak_can import AKMotor
from config import (KT_NOMINAL, LEVER_ARM_M, LEVER_ARM_OPTIONS, GEAR_RATIO,
                    POLE_PAIRS, SAFE_TORQUE_MAX)
from loadcell import LoadCell
from logger import RateLimiter, Recorder, SafetyTripped, check_safety


# ==================================================================
# 共用：一個「保持指令 N 秒並持續記錄」的小函式
# ==================================================================
def hold(motor, lc, rec, phase, seconds, cmd_torque=0.0, cmd_velocity=0.0):
    rl = RateLimiter()
    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        ms, _ = rec.snapshot(motor, lc, phase, cmd_torque, cmd_velocity)
        check_safety(ms)
        rl.wait()


# ==================================================================
# 實驗 0：縮放常數驗證  ★ 這是所有實驗的前提，不做這個後面全部沒意義
# ==================================================================
def exp_verify_scaling():
    """
    要驗證兩件事，都是靠「拿一個可信的量測去對照一個可疑的換算」：

    (A) 位置回授的單位是不是輸出軸的度數？
        做法：用手把力臂轉 90°（拿量角器或直角尺比），看回授位置變化多少。
              變 90 → 對，是輸出軸角度
              變 810 (=90×9) → 是馬達端角度，要自己除以減速比
              變其他數字 → 縮放常數錯了，回頭查手冊版本

    (B) POLE_PAIRS 對不對？
        做法：讓馬達等速轉，比對兩個速度來源：
              來源一（可疑）：回授 eRPM ÷ POLE_PAIRS ÷ GEAR_RATIO 換算的 rad/s
              來源二（可信）：位置回授對時間微分
              兩者比值就是你的 POLE_PAIRS 修正倍率。
    """
    print(__doc__ if False else "")
    with AKMotor() as motor:
        # ---- (A) 位置 ----
        motor.idle()
        time.sleep(0.5)
        s0 = motor.read()
        if s0 is None:
            print("★ 收不到馬達回授。檢查：CAN 線、120Ω 終端電阻、馬達 ID、bitrate")
            return
        print(f"\n[A] 目前位置回授 = {s0.pos_deg:.2f} 度")
        input("    請用手把輸出軸轉大約 +90 度（用直角尺比），轉好後按 Enter：")
        s1 = motor.read()
        d = s1.pos_deg - s0.pos_deg
        print(f"    位置變化 = {d:.2f}")
        print(f"    → 若 ≈90 : 回授是輸出軸角度（大多數 V3.0 韌體如此）")
        print(f"    → 若 ≈810: 回授是馬達端角度，spd/pos 都要再除以 {GEAR_RATIO}")

        # ---- (B) 速度 ----
        input("\n[B] 確認力臂已拆下、輸出軸可自由旋轉，按 Enter 開始低速旋轉測試：")
        motor.velocity(2.0, kd=2.0)      # 2 rad/s 慢慢轉
        time.sleep(1.5)                  # 等它到穩態
        samples = []
        t_end = time.perf_counter() + 3.0
        while time.perf_counter() < t_end:
            st = motor.read()
            if st:
                samples.append((st.t, st.pos_deg, st.spd_erpm, st.spd_rads))
            time.sleep(0.005)
        motor.idle()

        if len(samples) < 20:
            print("    樣本太少，檢查回授頻率設定")
            return
        t_a, p_a = samples[0][0], samples[0][1]
        t_b, p_b = samples[-1][0], samples[-1][1]
        v_from_pos = math.radians(p_b - p_a) / (t_b - t_a)
        v_from_erpm = sum(s[3] for s in samples) / len(samples)
        print(f"    位置微分算出的角速度  = {v_from_pos:+.4f} rad/s   ← 可信")
        print(f"    eRPM 換算的角速度     = {v_from_erpm:+.4f} rad/s   ← 待驗證")
        if abs(v_from_erpm) > 1e-6:
            ratio = v_from_pos / v_from_erpm
            print(f"    比值 = {ratio:.4f}")
            print(f"    → 正確的 POLE_PAIRS ≈ {POLE_PAIRS / ratio:.1f}"
                  f"（目前設 {POLE_PAIRS}）")
            print(f"    → 把這個整數填回 config.py")


# ==================================================================
# 實驗 1：扭力常數校正掃描  → 交付物「實測 Kt vs 標稱 Kt」
# ==================================================================
def exp_kt_calibration(t_max=None, n_steps=10, hold_s=3.0, rest_s=5.0):
    """
    這是最核心的一組。做法是階梯式掃描指令扭力，每一階停住，
    同時記錄「指令扭力」「回授電流」「load cell 實測扭力」。

    分析時你會得到三條關係：
      實測扭力 vs 回授電流  → 真實的 Kt（含減速比與傳動效率）
      實測扭力 vs 指令扭力  → 驅動器的指令準確度
      線性度何時開始崩壞    → 磁飽和點，也就是你真正的可用峰值扭力

    ★ 每一階之間要 rest_s 秒的無載休息，否則溫度會單調上升，
      你分不出「扭力下降是因為飽和還是因為變熱」。這兩個效應必須分開量。
    """
    t_max = t_max or SAFE_TORQUE_MAX
    steps = [t_max * (i + 1) / n_steps for i in range(n_steps)]

    with AKMotor() as motor, LoadCell() as lc:
        lc.tare()
        with Recorder("kt_calib") as rec:
            try:
                hold(motor, lc, rec, "zero", 2.0)
                for tq in steps:
                    print(f"  指令 {tq:5.2f} N·m ...", end="", flush=True)
                    motor.torque(tq)
                    hold(motor, lc, rec, f"step_{tq:.2f}", hold_s, cmd_torque=tq)
                    motor.idle()
                    hold(motor, lc, rec, "rest", rest_s)
                    st = motor.read()
                    print(f" 溫度 {st.temp_c:.0f}°C")
            except (SafetyTripped, KeyboardInterrupt) as e:
                print(f"\n中止：{e}")
            finally:
                motor.idle()


# ==================================================================
# 實驗 2：正反向不對稱（你問的「抬重物」vs「往下頂」）
# ==================================================================
def exp_direction_asymmetry(t_max=None, n_steps=8, hold_s=3.0, rest_s=4.0):
    """
    同樣的扭力大小，正轉（抬）與反轉（頂）量出來會不會不一樣？

    可能造成不對稱的原因：驅動器的電流環調校、行星齒輪的齒面接觸、
    軸承預壓、以及你的治具本身（力臂受拉與受壓的變形量不同）。

    ★ 治具因素要先排除：用 S 型 load cell（拉壓兩用）而不是兩顆單向的，
      否則你量到的不對稱有一半是治具造成的。

    做法：正負交錯掃描（+1, -1, +2, -2, ...），不要先掃完正的再掃負的。
    交錯的目的是讓溫度漂移對正反兩向的影響均等，這樣兩者相減時會抵消。
    """
    t_max = t_max or SAFE_TORQUE_MAX
    mags = [t_max * (i + 1) / n_steps for i in range(n_steps)]

    with AKMotor() as motor, LoadCell() as lc:
        lc.tare()
        with Recorder("direction_asym") as rec:
            try:
                for m in mags:
                    for sign in (+1, -1):
                        tq = sign * m
                        print(f"  指令 {tq:+6.2f} N·m")
                        motor.torque(tq)
                        hold(motor, lc, rec, f"dir_{tq:+.2f}", hold_s, cmd_torque=tq)
                        motor.idle()
                        hold(motor, lc, rec, "rest", rest_s)
            except (SafetyTripped, KeyboardInterrupt) as e:
                print(f"\n中止：{e}")
            finally:
                motor.idle()


# ==================================================================
# 實驗 3：可反向驅動阻力  ★ 這一組直接是你論文的「可反向驅動性」指標
# ==================================================================
def exp_backdrive(duration=60.0):
    """
    馬達完全不通電（kp=kd=t_ff=0），由人從力臂端緩慢來回推動，
    量測「推動它所需要的力矩」。這個力矩就是折算到輸出端的摩擦 + 齒隙 + 阻尼。

    為什麼這是你研究的關鍵指標：
      SPU 架構多了螺桿，如果是自鎖型，這個值會大到讓 QDD 的低摩擦優勢完全消失，
      控制組想做的柔順著陸就做不出來。RSU 沒有螺桿，這個值只有球接頭的摩擦。
      這一組數據就是你「把控制端需求納入機構最佳化」那個新指標的實體量測基礎。

    推的時候要慢（<0.5 rad/s），目的是量靜/庫倫摩擦而不是黏滯阻尼。
    如果你想分離「庫倫摩擦」和「黏滯阻尼」，就分別用慢速和快速各推一輪，
    畫「阻力 vs 速度」圖，截距是庫倫項、斜率是黏滯項。

    ★ 之後你有第二種傳動模組時，跑同一支腳本、比同一個數字，這就是對照實驗。
    """
    with AKMotor() as motor, LoadCell() as lc:
        lc.tare()
        motor.idle()
        print("  馬達已放空。請用手緩慢來回推動力臂（正反各數次，越慢越好）")
        print(f"  記錄 {duration:.0f} 秒，Ctrl-C 可提前結束")
        with Recorder("backdrive") as rec:
            try:
                hold(motor, lc, rec, "backdrive", duration)
            except (SafetyTripped, KeyboardInterrupt) as e:
                print(f"\n結束：{e}")
            finally:
                motor.idle()


# ==================================================================
# 實驗 4：熱衰減  → 直接接你甘特圖第 8-12 週的熱特性化
# ==================================================================
def exp_thermal(torque=None, duration=600.0, mount_label="stock"):
    """
    固定扭力長時間輸出，記錄溫度上升與實測扭力隨時間的衰減。

    mount_label 這個參數是重點：跑完一次改一種固定座再跑一次，
    標籤填 "pla" / "alu" / "alu_fin" / "alu_paste"，之後就能把四條溫升曲線疊在一起。
    這正是你研究裡「商用致動器的外部散熱設計」那一塊的原始數據。

    要抓的三個數字：
      熱時間常數 τ  ── 溫度上升到穩態值 63.2% 所需時間
      穩態溫升 ΔT∞  ── 決定可持續扭力上限
      扭力衰減率     ── 同樣指令下實測扭力隨溫度下降多少（繞組電阻隨溫上升）

    ★ 你照片裡那顆是 3D 列印的塑膠底座 —— 那正好就是你的 baseline（最差情況）。
      先量它，再量鋁座，對比會很明顯，圖也好看。
    """
    torque = torque if torque is not None else SAFE_TORQUE_MAX * 0.5
    with AKMotor() as motor, LoadCell() as lc:
        lc.tare()
        with Recorder(f"thermal_{mount_label}") as rec:
            try:
                hold(motor, lc, rec, "pre", 10.0)
                print(f"  固定 {torque:.2f} N·m，持續 {duration/60:.0f} 分鐘")
                motor.torque(torque)
                rl = RateLimiter()
                t_end = time.perf_counter() + duration
                last_print = 0.0
                while time.perf_counter() < t_end:
                    ms, _ = rec.snapshot(motor, lc, "soak", cmd_torque=torque)
                    check_safety(ms)
                    now = time.perf_counter()
                    if ms and now - last_print > 10:
                        print(f"    t={rec.n/200:6.0f}s  {ms.temp_c:5.1f}°C  "
                              f"{ms.current_a:6.2f}A")
                        last_print = now
                    rl.wait()
                # 降溫曲線也要記，它給你另一組獨立的熱時間常數，可以互相驗證
                motor.idle()
                print("  進入降溫記錄（5 分鐘）")
                hold(motor, lc, rec, "cooldown", 300.0)
            except (SafetyTripped, KeyboardInterrupt) as e:
                print(f"\n中止：{e}")
            finally:
                motor.idle()


# ==================================================================
if __name__ == "__main__":
    table = {
        "verify": exp_verify_scaling,
        "kt": exp_kt_calibration,
        "asym": exp_direction_asymmetry,
        "backdrive": exp_backdrive,
        "thermal": exp_thermal,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in table:
        print("用法: python experiments.py [" + " | ".join(table) + "]")
        sys.exit(1)
    table[sys.argv[1]]()
