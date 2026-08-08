"""
analyze.py — 讀 CSV 出圖出數字

    python analyze.py data/20260805_143000_kt_calib.csv

會依 phase 欄自動判斷是哪一種實驗，跑對應的分析。
所有輸出（圖 + 摘要 txt）存到 data/analysis/ 底下。

設計原則：分析跟量測完全分開。量測時只管把原始數據寫下來，
一個數字都不要在現場算。這樣事後發現換算公式錯了，重跑分析就好，
不用重做實驗 —— 熱實驗跑一次要 15 分鐘，你不會想重做的。
"""

import os
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import GEAR_RATIO, KT_NOMINAL

OUT = "data/analysis"


def load(path):
    df = pd.read_csv(path)
    # 只留兩個通道都新鮮的資料列。50 ms 是個寬鬆的門檻，
    # 如果被剔掉很多列，代表你的 load cell 取樣率或 CAN 回授率太低。
    n0 = len(df)
    df = df[(df["age_can"].fillna(9) < 0.05) & (df["age_lc"].fillna(9) < 0.05)]
    print(f"[載入] {n0} 列 → 有效 {len(df)} 列 ({len(df)/max(n0,1)*100:.0f}%)")
    if len(df) < n0 * 0.8:
        print("  ⚠ 剔除比例偏高，檢查 HX711 是否設在 80 SPS、CAN 回授率是否夠")
    return df


def steady(df, phase, tail_frac=0.5):
    """取某個 phase 的後半段（已進入穩態）做平均。前半段是暫態，會汙染平均值。"""
    d = df[df["phase"] == phase]
    if len(d) == 0:
        return None
    return d.iloc[int(len(d) * (1 - tail_frac)):]


# ------------------------------------------------------------------
def analyze_kt(df, stem):
    phases = [p for p in df["phase"].unique() if str(p).startswith("step_")]
    rows = []
    for p in sorted(phases, key=lambda s: float(s.split("_")[1])):
        d = steady(df, p)
        if d is None or len(d) < 5:
            continue
        rows.append(dict(
            cmd=float(p.split("_")[1]),
            current=d["current_a"].mean(),
            torque=d["torque_meas"].mean(),
            torque_sd=d["torque_meas"].std(),
            temp=d["temp_c"].mean(),
        ))
    r = pd.DataFrame(rows)
    if len(r) < 3:
        print("資料點太少"); return

    # ★ Kt 必須只用「線性區」擬合。若把飽和區一起丟進去，
    #   擬合出來的斜率會被拉低，你會誤以為 Kt 偏差比實際更大。
    #   做法：用前 40% 的低電流點先擬一條基準線，再往上找第一個
    #   偏離超過 5% 的點當作飽和起點。
    def fit_through_origin(d):
        return float((d["current"] * d["torque"]).sum() / (d["current"] ** 2).sum())

    n_lin = max(3, int(len(r) * 0.4))
    kt_lin = fit_through_origin(r.iloc[:n_lin])
    sat_i = None
    for i in range(n_lin, len(r)):
        pred = kt_lin * r["current"].iloc[i]
        if pred > 0 and (r["torque"].iloc[i] - pred) / pred < -0.05:
            sat_i = i
            break
    lin = r if sat_i is None else r.iloc[:sat_i]
    kt_out = fit_through_origin(lin)
    kt_all = fit_through_origin(r)
    kt_motor = kt_out / GEAR_RATIO
    resid = r["torque"] - kt_out * r["current"]
    rl = lin["torque"] - kt_out * lin["current"]
    r2 = 1 - (rl ** 2).sum() / ((lin["torque"] - lin["torque"].mean()) ** 2).sum()
    sat_a = float(r["current"].iloc[sat_i]) if sat_i is not None else float("nan")

    # 指令準確度：同樣只看線性區
    ratio = (lin["torque"] / lin["cmd"]).mean()

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))

    ax[0].errorbar(r["current"], r["torque"], yerr=r["torque_sd"],
                   fmt="o", capsize=3, label="measured")
    xs = np.linspace(0, r["current"].max() * 1.05, 50)
    ax[0].plot(xs, kt_out * xs, "-",
               label=f"linear-region fit Kt={kt_out:.3f} N·m/A")
    ax[0].plot(xs, KT_NOMINAL * GEAR_RATIO * xs, "--",
               label=f"nominal Kt*n={KT_NOMINAL*GEAR_RATIO:.3f}")
    if sat_i is not None:
        ax[0].axvline(sat_a, color="r", ls=":", label=f"saturation @ {sat_a:.1f} A")
    ax[0].set_xlabel("phase current (A)"); ax[0].set_ylabel("measured torque (N·m)")
    ax[0].set_title(f"Kt calibration  (R²={r2:.4f})"); ax[0].legend(); ax[0].grid(alpha=.3)

    ax[1].plot(r["cmd"], r["torque"], "o-")
    lim = [0, max(r["cmd"].max(), r["torque"].max()) * 1.05]
    ax[1].plot(lim, lim, "k--", label="ideal 1:1")
    ax[1].set_xlabel("commanded torque (N·m)"); ax[1].set_ylabel("measured (N·m)")
    ax[1].set_title(f"command accuracy  (mean ratio={ratio:.3f})")
    ax[1].legend(); ax[1].grid(alpha=.3)

    # 殘差圖 —— 飽和點就在殘差開始系統性往下掉的地方
    ax[2].axhline(0, color="k", lw=.8)
    ax[2].plot(r["current"], resid, "o-")
    ax[2].set_xlabel("phase current (A)"); ax[2].set_ylabel("residual (N·m)")
    ax[2].set_title("linearity residual → saturation onset"); ax[2].grid(alpha=.3)

    fig.tight_layout(); fig.savefig(f"{OUT}/{stem}_kt.png", dpi=140)

    dev = (kt_out / (KT_NOMINAL * GEAR_RATIO) - 1) * 100
    sat_txt = (f"{sat_a:.1f} A（對應扭力約 {kt_out*sat_a:.1f} N·m）"
               if sat_i is not None else "未偵測到（掃描範圍內尚未飽和，可再往上掃）")
    summary = (
        f"實測 Kt（輸出端，含 {GEAR_RATIO}:1 減速，僅線性區）= {kt_out:.4f} N·m/A\n"
        f"折算馬達端 Kt                                   = {kt_motor:.4f} N·m/A\n"
        f"廠商標稱 Kt                                     = {KT_NOMINAL:.4f} N·m/A\n"
        f"偏差                                            = {dev:+.1f} %\n"
        f"線性區擬合 R²                                   = {r2:.5f}\n"
        f"（參考）全範圍擬合 Kt                           = {kt_all:.4f} N·m/A\n"
        f"飽和起點                                        = {sat_txt}\n"
        f"指令→實測 平均比值（線性區）                    = {ratio:.4f}\n"
        f"\n★ 偏差就是你交付物的核心數字。若 >10%，代表任何用 datasheet\n"
        f"  的 Kt 去推算扭力的最佳化都會系統性偏掉。\n"
        f"★ 「線性區 Kt」與「全範圍 Kt」差很多，就代表你確實掃進飽和區了。\n"
        f"  報告要用線性區的值，飽和點另外當成「可用峰值扭力」單獨報。\n"
        f"★ 若比值明顯不等於 1，很可能是 config 的 T_MAX 填錯了\n"
        f"  （手冊表格 54.0 vs 範例碼 65.0，比值 54/65=0.83）\n"
    )
    print(summary)
    open(f"{OUT}/{stem}_kt.txt", "w").write(summary)


# ------------------------------------------------------------------
def analyze_asym(df, stem):
    phases = [p for p in df["phase"].unique() if str(p).startswith("dir_")]
    rows = []
    for p in phases:
        d = steady(df, p)
        if d is None or len(d) < 5:
            continue
        rows.append(dict(cmd=float(p.split("_")[1]),
                         torque=d["torque_meas"].mean(),
                         current=d["current_a"].mean()))
    r = pd.DataFrame(rows).sort_values("cmd")
    pos = r[r["cmd"] > 0].reset_index(drop=True)
    neg = r[r["cmd"] < 0].iloc[::-1].reset_index(drop=True)
    n = min(len(pos), len(neg))
    if n == 0:
        print("缺正向或反向資料"); return

    mag = pos["cmd"][:n].values
    asym = (pos["torque"][:n].values + neg["torque"][:n].values)  # 完美對稱應為 0
    rel = asym / mag * 100

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].plot(r["cmd"], r["torque"], "o-")
    ax[0].axhline(0, color="k", lw=.8); ax[0].axvline(0, color="k", lw=.8)
    ax[0].set_xlabel("commanded torque (N·m)"); ax[0].set_ylabel("measured (N·m)")
    ax[0].set_title("lift (+) vs press (−)"); ax[0].grid(alpha=.3)

    ax[1].bar(mag, rel)
    ax[1].set_xlabel("|torque| (N·m)"); ax[1].set_ylabel("asymmetry (%)")
    ax[1].set_title("directional asymmetry"); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/{stem}_asym.png", dpi=140)

    s = (f"平均不對稱度 = {np.mean(np.abs(rel)):.2f} %\n"
         f"最大不對稱度 = {np.max(np.abs(rel)):.2f} %\n"
         f"\n★ 3% 以內通常是量測雜訊，不必解讀。\n"
         f"★ 若超過 10%，先懷疑治具（力臂受拉/受壓變形不同、load cell 不垂直），\n"
         f"  把力臂反裝 180° 再跑一次：若不對稱方向跟著翻，就是治具問題；\n"
         f"  若方向不變，才是馬達本身的特性。\n")
    print(s); open(f"{OUT}/{stem}_asym.txt", "w").write(s)


# ------------------------------------------------------------------
def analyze_backdrive(df, stem):
    d = df[df["phase"] == "backdrive"].copy()
    if len(d) < 50:
        print("資料太少"); return
    d["v"] = d["spd_rads"]
    moving = d[d["v"].abs() > 0.02]

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].scatter(moving["v"], moving["torque_meas"], s=4, alpha=.3)
    ax[0].set_xlabel("angular velocity (rad/s)")
    ax[0].set_ylabel("resistive torque (N·m)")
    ax[0].set_title("backdrive resistance vs speed"); ax[0].grid(alpha=.3)

    # 分離庫倫摩擦與黏滯阻尼：τ = sign(v)·τ_c + b·v
    fw = moving[moving["v"] > 0]
    bw = moving[moving["v"] < 0]
    tc = fb = None
    if len(fw) > 20 and len(bw) > 20:
        cf = np.polyfit(fw["v"], fw["torque_meas"], 1)
        cb = np.polyfit(bw["v"], bw["torque_meas"], 1)
        tc = (abs(cf[1]) + abs(cb[1])) / 2          # 截距 → 庫倫摩擦
        fb = (cf[0] + cb[0]) / 2                    # 斜率 → 黏滯係數
        xs = np.linspace(moving["v"].min(), moving["v"].max(), 50)
        ax[0].plot(xs[xs > 0], np.polyval(cf, xs[xs > 0]), "r-")
        ax[0].plot(xs[xs < 0], np.polyval(cb, xs[xs < 0]), "r-")

    ax[1].hist(moving["torque_meas"].abs(), bins=40)
    ax[1].set_xlabel("|resistive torque| (N·m)"); ax[1].set_ylabel("count")
    ax[1].set_title("distribution"); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/{stem}_backdrive.png", dpi=140)

    s = (f"反驅阻力中位數 = {moving['torque_meas'].abs().median():.4f} N·m\n"
         f"反驅阻力 95%   = {moving['torque_meas'].abs().quantile(.95):.4f} N·m\n")
    if tc is not None:
        s += (f"庫倫摩擦 τ_c   = {tc:.4f} N·m\n"
              f"黏滯係數 b     = {fb:.5f} N·m·s/rad\n")
    s += ("\n★ 這個數字就是你論文「可反向驅動性」指標的實體基準。\n"
          "  換上不同傳動模組（SPU / RSU）跑同一支腳本、比同一個中位數，\n"
          "  就是最乾淨的對照實驗。\n")
    print(s); open(f"{OUT}/{stem}_backdrive.txt", "w").write(s)


# ------------------------------------------------------------------
def analyze_thermal(df, stem):
    soak = df[df["phase"] == "soak"]
    cool = df[df["phase"] == "cooldown"]
    if len(soak) < 50:
        print("升溫段資料太少"); return

    t = soak["t"].values - soak["t"].values[0]
    T = soak["temp_c"].values
    T0 = T[:max(1, int(len(T) * .01))].mean()

    # ★ 不要用「升到 63.2% 的時間」當 τ。
    #   那個做法預設你已經跑到穩態；實務上熱實驗常常只跑到 2~3 個 τ，
    #   此時末端溫度還不是 T∞，用它當基準會系統性低估 τ（也低估 T∞）。
    #   正確做法：對整條曲線擬合 T(t) = T∞ − (T∞−T0)·exp(−t/τ)，
    #   讓 T∞ 和 τ 一起被解出來，即使沒跑到穩態也能外推。
    from scipy.optimize import curve_fit

    def model(tt, Tinf_, tau_, T0_):
        return Tinf_ - (Tinf_ - T0_) * np.exp(-tt / tau_)

    Tend = T[-int(len(T) * .05):].mean()
    try:
        p, _ = curve_fit(model, t, T, p0=[Tend + 5, max(t[-1] / 3, 1), T0],
                         maxfev=20000)
        Tinf, tau, T0 = float(p[0]), float(p[1]), float(p[2])
        fitted = True
    except Exception:
        Tinf, tau, fitted = Tend, float("nan"), False

    coverage = t[-1] / tau if (fitted and tau > 0) else float("nan")

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    ax[0].plot(t, T, label="heating", lw=.8)
    if len(cool) > 10:
        tc = cool["t"].values - cool["t"].values[0]
        ax[0].plot(tc + t[-1], cool["temp_c"].values, label="cooling", lw=.8)
    if fitted:
        ax[0].plot(t, model(t, Tinf, tau, T0), "r--",
                   label=f"fit: tau={tau:.0f}s")
        ax[0].axhline(Tinf, ls=":", c="gray", label=f"T_inf={Tinf:.1f}C (extrap.)")
    ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("driver temp (°C)")
    ax[0].set_title("thermal response"); ax[0].legend(); ax[0].grid(alpha=.3)

    ax[1].plot(t, soak["torque_meas"].values, lw=.6)
    ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("measured torque (N·m)")
    ax[1].set_title("torque fade under constant command"); ax[1].grid(alpha=.3)

    ax[2].scatter(T, soak["torque_meas"].values, s=3, alpha=.3)
    ax[2].set_xlabel("temp (°C)"); ax[2].set_ylabel("torque (N·m)")
    ax[2].set_title("torque vs temperature"); ax[2].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/{stem}_thermal.png", dpi=140)

    tq0 = soak["torque_meas"].iloc[:int(len(soak) * .05)].mean()
    tq1 = soak["torque_meas"].iloc[-int(len(soak) * .05):].mean()
    s = (f"起始溫度        = {T0:.1f} °C\n"
         f"實驗末端溫度    = {Tend:.1f} °C（實測）\n"
         f"穩態溫度 T∞     = {Tinf:.1f} °C（指數擬合外推，溫升 {Tinf-T0:.1f} K）\n"
         f"熱時間常數 τ    = {tau:.0f} s\n"
         f"實驗長度 / τ    = {coverage:.1f}   ← 這個數字很重要\n"
         f"扭力衰減        = {tq0:.3f} → {tq1:.3f} N·m ({(tq1/tq0-1)*100:+.1f} %)\n"
         f"\n★ 「實驗長度/τ」小於 3 代表你根本沒跑到穩態，T∞ 是外推出來的，\n"
         f"  誤差會比較大。要有把握的 T∞，實驗長度至少要 4~5 個 τ。\n"
         f"  這也是為什麼不能用「升到 63.2% 的時間」當 τ —— 那個做法\n"
         f"  預設你已經在穩態，沒跑到就會同時低估 τ 和 T∞。\n"
         f"★ 注意這是「驅動板」溫度，不是繞組溫度。繞組會更高、上升更快。\n"
         f"  若要推繞組溫度，需要外貼 NTC 在定子側，或用熱像儀從外殼推。\n"
         f"★ 換不同固定座材質重跑，把幾條 T∞ 與 τ 並排，就是你熱特性化的主圖。\n")
    print(s); open(f"{OUT}/{stem}_thermal.txt", "w").write(s)


# ------------------------------------------------------------------
def analyze_file(path, output_dir=None):
    """Analyze one recorder CSV and return the generated image paths."""
    global OUT
    path = str(path)
    if output_dir is not None:
        OUT = str(output_dir)
    os.makedirs(OUT, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    df = load(path)
    ph = set(df["phase"].astype(str))

    if any(p.startswith("step_") for p in ph):
        analyze_kt(df, stem)
    elif any(p.startswith("dir_") for p in ph):
        analyze_asym(df, stem)
    elif "backdrive" in ph:
        analyze_backdrive(df, stem)
    elif "soak" in ph:
        analyze_thermal(df, stem)
    else:
        raise ValueError(f"認不出實驗類型，phase 欄含：{ph}")
    return sorted(Path(OUT).glob(f"{stem}_*.png"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze.py data/xxx.csv"); sys.exit(1)
    analyze_file(sys.argv[1])
