"""
simulate.py — 產生假資料，讓你「今天、沒有硬體」就能把整條分析流程跑通

    python simulate.py          # 產生四組假 CSV 到 data/
    python analyze.py data/sim_kt_calib.csv

為什麼要有這支：等你 load cell 到貨、接線接好、Arduino 校正完，可能是兩週後。
但分析程式的 bug 現在就可以抓完。硬體到位那天你只要跑實驗，
不用一邊處理接線一邊 debug pandas —— 那是最容易出錯的情境。

假資料裡我故意塞了三個「真實會遇到的現象」：
  1. 實測 Kt 比標稱低 8%（傳動效率損失）
  2. 高電流時輕微飽和
  3. 溫度上升造成扭力衰減
跑一次 analyze.py，看它有沒有把這三件事抓出來。
"""

import csv
import math
import os
import random

import numpy as np

from config import GEAR_RATIO, KT_NOMINAL, LEVER_ARM_M
from logger import COLUMNS

os.makedirs("data", exist_ok=True)
RATE = 200
KT_TRUE = KT_NOMINAL * GEAR_RATIO * 0.92     # ← 真值比標稱低 8%
SAT_A = 12.0                                 # 超過這個電流開始飽和


def writer(name):
    f = open(f"data/sim_{name}.csv", "w", newline="")
    w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader()
    return f, w


def row(t, phase, cmd_t=0.0, cmd_v=0.0, cur=0.0, tq=0.0, temp=25.0,
        pos=0.0, spd=0.0):
    return dict(t=round(t, 5), phase=phase, cmd_torque=cmd_t, cmd_velocity=cmd_v,
                pos_deg=round(pos, 3), spd_rads=round(spd, 4),
                spd_erpm=round(spd * 21 * 9 * 60 / (2 * math.pi), 1),
                current_a=round(cur, 4), temp_c=round(temp, 1), error=0,
                force_n=round(tq / LEVER_ARM_M, 4), torque_meas=round(tq, 5),
                lever_m=LEVER_ARM_M, age_can=0.004, age_lc=0.012)


def torque_of(cur, temp):
    """含飽和 + 溫度衰減的真實響應"""
    tq = KT_TRUE * cur
    if cur > SAT_A:                       # 磁飽和：超過門檻後增益打七折
        tq = KT_TRUE * SAT_A + KT_TRUE * 0.7 * (cur - SAT_A)
    tq *= (1 - 0.0009 * (temp - 25))      # 溫度每升 1°C 掉 0.09%
    return tq + random.gauss(0, 0.012)


# ---------- Kt 校正 ----------
f, w = writer("kt_calib"); t = 0.0; temp = 25.0
for k in range(1, 11):
    cmd = 20.0 * k / 10
    cur = cmd / KT_NOMINAL / GEAR_RATIO
    for _ in range(3 * RATE):
        temp += 0.0016 * cur
        w.writerow(row(t, f"step_{cmd:.2f}", cmd_t=cmd, cur=cur + random.gauss(0, .05),
                       tq=torque_of(cur, temp), temp=temp)); t += 1 / RATE
    for _ in range(5 * RATE):
        temp -= 0.004
        w.writerow(row(t, "rest", temp=temp)); t += 1 / RATE
f.close()

# ---------- 正反向不對稱 ----------
f, w = writer("direction_asym"); t = 0.0; temp = 25.0
for k in range(1, 9):
    mag = 20.0 * k / 8
    for sign in (+1, -1):
        cmd = sign * mag
        cur = cmd / KT_NOMINAL / GEAR_RATIO
        # 反向多 4% 的損失（模擬齒面接觸差異）
        eff = 1.0 if sign > 0 else 0.96
        for _ in range(3 * RATE):
            temp += 0.0016 * abs(cur)
            w.writerow(row(t, f"dir_{cmd:+.2f}", cmd_t=cmd,
                           cur=cur + random.gauss(0, .05),
                           tq=torque_of(cur, temp) * eff, temp=temp)); t += 1 / RATE
        for _ in range(4 * RATE):
            temp -= 0.004
            w.writerow(row(t, "rest", temp=temp)); t += 1 / RATE
f.close()

# ---------- 反驅阻力 ----------
f, w = writer("backdrive"); t = 0.0
TAU_C, B = 0.45, 0.030          # 庫倫摩擦 0.45 N·m，黏滯 0.030
for i in range(60 * RATE):
    v = 0.35 * math.sin(2 * math.pi * t / 8)
    tq = (math.copysign(TAU_C, v) + B * v + random.gauss(0, .02)) if abs(v) > .02 else random.gauss(0, .02)
    w.writerow(row(t, "backdrive", tq=tq, spd=v,
                   pos=-0.35 * 8 / (2 * math.pi) * math.cos(2 * math.pi * t / 8) * 57.3))
    t += 1 / RATE
f.close()

# ---------- 熱衰減 ----------
f, w = writer("thermal_pla"); t = 0.0
T0, TINF, TAU = 25.0, 78.0, 240.0
cmd = 10.0; cur = cmd / KT_NOMINAL / GEAR_RATIO
for _ in range(10 * RATE):
    w.writerow(row(t, "pre", temp=T0)); t += 1 / RATE
t_soak = 0.0
for _ in range(600 * RATE):
    temp = TINF - (TINF - T0) * math.exp(-t_soak / TAU) + random.gauss(0, .15)
    w.writerow(row(t, "soak", cmd_t=cmd, cur=cur + random.gauss(0, .05),
                   tq=torque_of(cur, temp), temp=temp))
    t += 1 / RATE; t_soak += 1 / RATE
Tend = TINF - (TINF - T0) * math.exp(-t_soak / TAU)
t_c = 0.0
for _ in range(300 * RATE):
    temp = T0 + (Tend - T0) * math.exp(-t_c / (TAU * 1.6)) + random.gauss(0, .15)
    w.writerow(row(t, "cooldown", temp=temp)); t += 1 / RATE; t_c += 1 / RATE
f.close()

print("已產生：")
for n in ("kt_calib", "direction_asym", "backdrive", "thermal_pla"):
    p = f"data/sim_{n}.csv"
    print(f"  {p}  ({os.path.getsize(p)/1e6:.1f} MB)")
print("\n接著跑：  python analyze.py data/sim_kt_calib.csv")
print("真值（拿來對答案）：")
print(f"  Kt 輸出端 = {KT_TRUE:.4f} N·m/A（標稱 {KT_NOMINAL*GEAR_RATIO:.4f}，低 8%）")
print(f"  飽和起點  = {SAT_A} A")
print(f"  庫倫摩擦  = {TAU_C} N·m,  黏滯 = {B}")
print(f"  熱時間常數 = {TAU} s,  穩態溫度 = {TINF} °C")
