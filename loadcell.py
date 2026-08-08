"""
loadcell.py — load cell 讀取層

架構：Arduino/ESP32 接 HX711，用 USB 序列埠把讀值持續吐給電腦，
      Python 這邊開一個執行緒不停收。

為什麼不直接用 Python 讀 HX711？
  HX711 是同步串列協議，時序要求嚴格（微秒等級）。作業系統會隨時打斷你的
  Python 程式，時序一亂讀出來就是垃圾。所以時序敏感的部分交給 MCU 做，
  Python 只負責收「已經處理好的數字」。這是量測系統的通則。

Arduino 端的 sketch 放在 arduino_loadcell/arduino_loadcell.ino
它每筆輸出一行：  <MCU毫秒>,<原始讀值>,<已扣皮重的公克數>\n
"""

import threading
import time
from dataclasses import dataclass

import serial

from config import LOADCELL_BAUD, LOADCELL_PORT, LOADCELL_SIGN

G = 9.80665


@dataclass
class ForceSample:
    t: float          # 電腦端時戳 (perf_counter)
    t_mcu_ms: int     # MCU 端時戳，用來檢查有沒有掉包
    raw: int
    grams: float
    newton: float


class LoadCell:
    def __init__(self, port=LOADCELL_PORT, baud=LOADCELL_BAUD,
                 sign=LOADCELL_SIGN):
        self.port, self.baud = port, baud
        self.sign = sign
        self.ser = None
        self.sample: ForceSample | None = None
        self._lock = threading.Lock()
        self._running = False
        self._zero_g = 0.0     # 軟體歸零偏移

    def open(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0.2)
        time.sleep(2.0)          # Arduino 開埠會重開機，等它起來
        self.ser.reset_input_buffer()
        self._running = True
        threading.Thread(target=self._rx_loop, daemon=True).start()
        # 等第一筆資料進來，確認真的通了
        t0 = time.time()
        while self.sample is None:
            if time.time() - t0 > 5:
                raise RuntimeError("load cell 沒有資料，檢查序列埠與接線")
            time.sleep(0.05)

    def close(self):
        self._running = False
        time.sleep(0.05)
        if self.ser:
            self.ser.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def _rx_loop(self):
        while self._running:
            try:
                line = self.ser.readline().decode("ascii", "ignore").strip()
            except Exception:
                continue
            if not line:
                continue
            parts = line.split(",")
            if len(parts) != 3:
                continue
            try:
                t_mcu, raw, grams = int(parts[0]), int(parts[1]), float(parts[2])
            except ValueError:
                continue
            grams = (grams - self._zero_g) * self.sign
            s = ForceSample(
                t=time.perf_counter(), t_mcu_ms=t_mcu, raw=raw,
                grams=grams, newton=grams / 1000.0 * G,
            )
            with self._lock:
                self.sample = s

    # -------- 對外介面 --------
    def read(self) -> ForceSample | None:
        with self._lock:
            return self.sample

    def tare(self, seconds: float = 2.0):
        """
        歸零。★ 每次實驗開始前都要做，而且是在「力臂已裝好、馬達未通電」的狀態下做。
        這樣才會把力臂自重、預壓一併扣掉。
        """
        self._zero_g = 0.0
        vals = []
        t0 = time.perf_counter()
        last = None
        while time.perf_counter() - t0 < seconds:
            s = self.read()
            if s and s is not last:
                vals.append(s.grams)
                last = s
            time.sleep(0.005)
        if not vals:
            raise RuntimeError("tare 期間沒收到資料")
        # vals 已套用方向符號；偏移量則必須保存在套用符號前的座標系。
        # 否則 sign=-1 時，第二次之後的讀值會把皮重加回去。
        self._zero_g = sum(vals) / len(vals) / self.sign
        noise = max(vals) - min(vals)
        print(f"[load cell] 歸零於 {self._zero_g:.2f} g，"
              f"雜訊峰對峰 {noise:.2f} g（{len(vals)} 筆）")
        # 雜訊太大代表接線/屏蔽有問題，先解決再往下做
        return noise


def torque_from_force(newton: float, lever_m: float) -> float:
    """力 → 扭力。就這麼一行，但方向與垂直度要對，見 README。"""
    return newton * lever_m


if __name__ == "__main__":
    # 單機測試：接好後跑這支，用手壓力臂看數字有沒有動
    with LoadCell() as lc:
        lc.tare()
        print("開始讀取，Ctrl-C 結束。用手壓/拉力臂試試看：")
        try:
            while True:
                s = lc.read()
                if s:
                    print(f"\r{s.grams:+9.1f} g  {s.newton:+8.2f} N  "
                          f"→ 扭力 {torque_from_force(s.newton, 0.15):+7.3f} N·m",
                          end="")
                time.sleep(0.05)
        except KeyboardInterrupt:
            print()
