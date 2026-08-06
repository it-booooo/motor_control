"""
logger.py — 同步時戳記錄

核心問題：你有兩個獨立的資料來源（CAN 上的馬達、序列埠上的 load cell），
它們各自用自己的節奏送資料，而你需要知道「這個扭力對應到哪個電流」。

錯誤做法：開兩支程式各自寫 CSV，事後用檔案時間對齊。
         → 兩支程式的時鐘起點不同、作業系統排程延遲不同，永遠對不準。

正確做法（這支檔案在做的）：
  同一支程式、同一個時鐘（time.perf_counter），固定頻率去「快照」兩邊的最新值，
  寫成一列。同時記錄每個值的「年齡」(age)，也就是這筆值是多久以前收到的。
  age 太大就代表那個通道當下沒有新資料，分析時可以把那些列剔掉。
  ★ 記錄 age 這件事很多人不做，但它是你判斷資料可不可信的唯一依據。
"""

import csv
import os
import time
from datetime import datetime

from ak_can import ERROR_TEXT, AKMotor
from config import (LEVER_ARM_M, LOG_DIR, LOG_RATE_HZ, SAFE_CURRENT_A,
                    SAFE_TEMP_C)
from loadcell import LoadCell, torque_from_force

COLUMNS = [
    "t",              # 相對時間 (s)，實驗開始為 0
    "phase",          # 實驗階段標籤，例如 "step_2.0Nm"，分析時用來分組
    "cmd_torque",     # 指令扭力 (N·m)
    "cmd_velocity",   # 指令速度 (rad/s)
    "pos_deg",        # 馬達回授位置 (度)
    "spd_rads",       # 馬達回授角速度 (rad/s，已換算)
    "spd_erpm",       # 原始電氣轉速，保留下來供驗算
    "current_a",      # 相電流 (A)
    "temp_c",         # 驅動板溫度
    "error",          # 錯誤碼
    "force_n",        # load cell 力 (N)
    "torque_meas",    # 實測扭力 = force_n × 力臂
    "lever_m",        # 當下的力臂長度，換孔位時要記得改 config 或傳參數
    "age_can",        # 馬達資料年齡 (s)
    "age_lc",         # load cell 資料年齡 (s)
]


class Recorder:
    def __init__(self, name: str, lever_m: float = LEVER_ARM_M):
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(LOG_DIR, f"{stamp}_{name}.csv")
        self.f = open(self.path, "w", newline="")
        self.w = csv.DictWriter(self.f, fieldnames=COLUMNS)
        self.w.writeheader()
        self.t0 = time.perf_counter()
        self.lever_m = lever_m
        self.n = 0

    def snapshot(self, motor: AKMotor, lc: LoadCell,
                 phase: str, cmd_torque=0.0, cmd_velocity=0.0):
        now = time.perf_counter()
        ms = motor.read()
        fs = lc.read() if lc else None

        row = {c: "" for c in COLUMNS}
        row["t"] = round(now - self.t0, 5)
        row["phase"] = phase
        row["cmd_torque"] = cmd_torque
        row["cmd_velocity"] = cmd_velocity
        row["lever_m"] = self.lever_m

        if ms:
            row.update(pos_deg=ms.pos_deg, spd_rads=round(ms.spd_rads, 4),
                       spd_erpm=ms.spd_erpm, current_a=ms.current_a,
                       temp_c=ms.temp_c, error=ms.error,
                       age_can=round(now - ms.t, 5))
        if fs:
            tq = torque_from_force(fs.newton, self.lever_m)
            row.update(force_n=round(fs.newton, 4),
                       torque_meas=round(tq, 5),
                       age_lc=round(now - fs.t, 5))

        self.w.writerow(row)
        self.n += 1
        if self.n % 200 == 0:
            self.f.flush()
        return ms, fs

    def close(self):
        self.f.flush()
        self.f.close()
        print(f"[記錄] {self.n} 列 → {self.path}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class SafetyTripped(Exception):
    pass


def check_safety(ms):
    """
    每一次取樣都呼叫。任何一項超標就丟例外，讓上層的 finally 去關馬達。
    ★ 這是軟體層的保護，不能取代硬體 E-stop / 電源開關。
      力臂加重物在轉，出事是真的會受傷。
    """
    if ms is None:
        return
    if ms.error != 0:
        raise SafetyTripped(f"馬達回報錯誤 {ms.error}: {ERROR_TEXT.get(ms.error)}")
    if ms.temp_c > SAFE_TEMP_C:
        raise SafetyTripped(f"驅動板溫度 {ms.temp_c}°C 超過上限 {SAFE_TEMP_C}°C")
    if abs(ms.current_a) > SAFE_CURRENT_A:
        raise SafetyTripped(f"電流 {ms.current_a:.1f} A 超過上限 {SAFE_CURRENT_A} A")


class RateLimiter:
    """固定頻率迴圈。用累加而非 sleep(1/f)，避免誤差累積造成頻率漂移。"""

    def __init__(self, hz=LOG_RATE_HZ):
        self.period = 1.0 / hz
        self.next_t = time.perf_counter()

    def wait(self):
        self.next_t += self.period
        dt = self.next_t - time.perf_counter()
        if dt > 0:
            time.sleep(dt)
        else:
            self.next_t = time.perf_counter()   # 落後太多就重設，不要追
