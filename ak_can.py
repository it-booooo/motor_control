"""
ak_can.py — CubeMars AK10-9 V3.0 的 legacy Direct CAN（Debug）實作

這個檔案保留 python-can TX/RX 與既有 AK10-9 feedback 相容性。正式實驗路徑使用
MotorBackend → STM32MotorBackend；共用的 MIT Control Mode payload codec 位於
src/motors/mit_codec.py。此 legacy class 不可直接套用到其他 motor profile。

CAN frame 格式來源：AK Series Module Product Manual v3.0.0，
第 4.2 節（發送）與 4.3 節（回授）。MIT 是控制模式，不是通訊協定。
"""

import math
import struct
import threading
import time
from dataclasses import dataclass, replace

try:
    import can
except ImportError:  # Simulation/model tests do not require python-can.
    can = None

from src.models import CanStatistics
from src.motors.mit_codec import (
    encode_mit_command,
    float_to_uint as _float_to_uint,
    uint_to_float as _uint_to_float,
)
from src.motors.profiles import AK10_9_V3_KV60

from config import (
    CAN_BITRATE, CAN_CHANNEL, CAN_INTERFACE, GEAR_RATIO, KD_MAX, KD_MIN,
    KP_MAX, KP_MIN, MIT_MODE_ID, MOTOR_ID, P_MAX, P_MIN, POLE_PAIRS,
    T_MAX, T_MIN, V_MAX, V_MIN,
)


# ------------------------------------------------------------------
# 第一部分：定點數轉換
# ------------------------------------------------------------------
# MIT Control Mode 為了把 5 個浮點數塞進 8 bytes，把每個數字線性映射到固定位元寬的整數。
# 例如扭力用 12 bits：把 [-65, +65] 這個區間切成 4096 格。
# 所以扭力解析度 = 130/4096 ≈ 0.032 N·m —— 這就是你指令的最小刻度，
# 做 Kt 校正掃描時的步階不要小於這個值，不然你只是在送重複的指令。

def float_to_uint(x: float, x_min: float, x_max: float, bits: int) -> int:
    """浮點 → 無號整數。對應手冊的 float_to_uint()。"""
    return _float_to_uint(x, x_min, x_max, bits)


def uint_to_float(x_int: int, x_min: float, x_max: float, bits: int) -> float:
    """無號整數 → 浮點。回授解碼用。"""
    return _uint_to_float(x_int, x_min, x_max, bits)


# ------------------------------------------------------------------
# 第二部分：指令打包
# ------------------------------------------------------------------
# ★ 注意位元組順序！V3.0 是 KP, KD, 位置, 速度, 扭力
#   網路上大量的 AK 範例程式是「舊版 MIT 韌體」的順序（位置, 速度, KP, KD, 扭力）。
#   直接抄那些程式碼，馬達會有反應但行為完全錯亂，而且很難 debug。
#   下面這段是照 V3.0 手冊第 39-40 頁的 pack_cmd() 寫的。

def pack_mit_command(p_des: float, v_des: float,
                     kp: float, kd: float, t_ff: float) -> bytes:
    """
    p_des : 目標位置 (rad)
    v_des : 目標速度 (rad/s)
    kp    : 位置增益。設 0 = 不做位置控制
    kd    : 速度增益。設 0 = 不做速度控制
    t_ff  : 前饋扭力 (N·m)

    馬達實際輸出 ≈ kp*(p_des - p) + kd*(v_des - v) + t_ff
    → 想做「純扭力控制」（Kt 校正實驗要的），就令 kp=kd=0，只給 t_ff
    → 想做「純速度控制」（無載轉速實驗要的），就令 kp=0，給 kd 和 v_des
    """
    return encode_mit_command(
        p_des,
        v_des,
        kp,
        kd,
        t_ff,
        profile=AK10_9_V3_KV60,
    )


# ------------------------------------------------------------------
# 第三部分：回授解包
# ------------------------------------------------------------------
# ★ 這裡有兩個很重要、也很容易踩雷的點：
#
# 1. 馬達回傳的是「電流」不是「扭力」。
#    你在上位機看到的扭力是它拿標稱 Kt 乘出來的估計值，不是量測值。
#    實機使用前必須確認命令與馬達回授的方向及尺度。
#
# 2. 回傳的速度是「電氣轉速 (eRPM)」，不是輸出軸轉速。
#    機械轉速 = eRPM / 極對數 / 減速比
#    極對數如果填錯，你算出來的轉速會差一個整數倍，而且看起來很合理。
#    → verify_scaling() 會用「位置微分」來交叉驗證這件事。

@dataclass
class MotorState:
    t: float              # 時戳 (s)，用 perf_counter
    pos_deg: float        # 位置 (度)，手冊: int16 × 0.1
    pos_rad: float        # 位置 (rad)
    spd_erpm: float       # 電氣轉速 (rpm)，手冊: int16 × 10
    spd_rads: float       # 換算後的輸出軸角速度 (rad/s)  ← 依賴 POLE_PAIRS
    current_a: float      # 相電流 (A)，手冊: int16 × 0.01
    temp_c: float         # 驅動板溫度 (°C)，int8
    error: int            # 0=正常 1=馬達過溫 2=過流 3=過壓 4=欠壓
                          # 5=編碼器故障 6=MOS過溫 7=堵轉

ERROR_TEXT = {
    0: "OK", 1: "馬達過溫", 2: "過電流", 3: "過電壓", 4: "欠電壓",
    5: "編碼器故障", 6: "MOSFET 過溫", 7: "堵轉",
}


def unpack_feedback(data: bytes, t: float) -> MotorState:
    pos_int = struct.unpack(">h", data[0:2])[0]
    spd_int = struct.unpack(">h", data[2:4])[0]
    cur_int = struct.unpack(">h", data[4:6])[0]
    temp = struct.unpack("b", data[6:7])[0]
    err = data[7]

    pos_deg = pos_int * 0.1
    spd_erpm = spd_int * 10.0
    return MotorState(
        t=t,
        pos_deg=pos_deg,
        pos_rad=math.radians(pos_deg),
        spd_erpm=spd_erpm,
        spd_rads=spd_erpm / POLE_PAIRS / GEAR_RATIO * 2 * math.pi / 60.0,
        current_a=cur_int * 0.01,
        temp_c=float(temp),
        error=err,
    )


# ------------------------------------------------------------------
# 第四部分：馬達物件
# ------------------------------------------------------------------
# 設計重點：收發要分開在不同執行緒。
# 原因是 MIT Control Mode 的馬達會「保持最後一筆指令直到收到新的」，
# 如果你的主程式因為寫檔案卡住 0.5 秒沒送指令，馬達會繼續用舊指令全力輸出。
# 所以送指令要有自己的固定頻率迴圈，跟你的實驗邏輯解耦。

class AKMotor:
    def __init__(self, motor_id: int = MOTOR_ID, *, interface: str = CAN_INTERFACE,
                 channel: str = CAN_CHANNEL, bitrate: int = CAN_BITRATE,
                 command_rate_hz: float = 200.0):
        self.motor_id = motor_id
        self.tx_id = (MIT_MODE_ID << 8) | motor_id   # 擴展幀 ID
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.command_rate_hz = command_rate_hz
        self.bus = None

        # 最新一筆回授（由接收執行緒更新，主執行緒讀）
        self.state: MotorState | None = None
        self._lock = threading.Lock()

        # 目前要送出的指令（由主執行緒寫，發送執行緒讀）
        self._cmd = pack_mit_command(0, 0, 0, 0, 0)
        self._running = False
        self._rx_thread = None
        self._tx_thread = None
        self._can_statistics = CanStatistics(
            can_tx_count=0,
            can_rx_count=0,
            can_tx_error=0,
            can_rx_error=0,
            rx_timeout_count=0,
            filtered_frame_count=0,
            bus_off_count=0,
        )

    # -------- 連線 --------
    def open(self):
        if can is None:
            raise RuntimeError("python-can is required for Direct CAN backend")
        self.bus = can.interface.Bus(
            interface=self.interface, channel=self.channel, bitrate=self.bitrate
        )
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx_thread.start()
        self._tx_thread.start()

    def close(self):
        """一定要用 try/finally 呼叫這個。忘記關 = 馬達持續出力。"""
        self.set_command(0, 0, 0, 0, 0)
        time.sleep(0.05)
        self._running = False
        time.sleep(0.05)
        if self.bus:
            self.bus.shutdown()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    # -------- 背景迴圈 --------
    def _tx_loop(self):
        period = 1.0 / self.command_rate_hz
        next_t = time.perf_counter()
        while self._running:
            msg = can.Message(arbitration_id=self.tx_id,
                              data=self._cmd,
                              is_extended_id=True)
            try:
                self.bus.send(msg)
                self._can_statistics.can_tx_count += 1
            except can.CanError as exc:
                self._can_statistics.can_tx_error += 1
                self._can_statistics.last_error = str(exc)
            next_t += period
            time.sleep(max(0.0, next_t - time.perf_counter()))

    def _rx_loop(self):
        while self._running:
            try:
                msg = self.bus.recv(timeout=0.1)
            except can.CanError as exc:
                self._can_statistics.can_rx_error += 1
                self._can_statistics.last_error = str(exc)
                continue
            if msg is None:
                self._can_statistics.rx_timeout_count += 1
                continue
            if len(msg.data) < 8:
                self._can_statistics.filtered_frame_count += 1
                continue
            self._can_statistics.can_rx_count += 1
            st = unpack_feedback(msg.data, time.perf_counter())
            with self._lock:
                self.state = st

    # -------- 對外介面 --------
    def set_command(self, p_des=0.0, v_des=0.0, kp=0.0, kd=0.0, t_ff=0.0):
        self._cmd = pack_mit_command(p_des, v_des, kp, kd, t_ff)

    def torque(self, t_ff: float):
        """MIT Control Mode torque preset：kp=kd=0，只使用 feedforward。"""
        self.set_command(0, 0, 0, 0, t_ff)

    def velocity(self, v_rads: float, kd: float = 2.0):
        """MIT Control Mode velocity preset：kp=0；不是 native Velocity Mode。"""
        self.set_command(0, v_rads, 0, kd, 0)

    def idle(self):
        """完全放空 —— 量可反向驅動阻力時用這個"""
        self.set_command(0, 0, 0, 0, 0)

    def read(self) -> MotorState | None:
        with self._lock:
            return self.state

    def get_can_statistics(self) -> CanStatistics:
        """Direct-CAN counters measured by python-can, not STM32 counters."""

        return replace(self._can_statistics)


# ------------------------------------------------------------------
# 自我測試：不接馬達也能跑，驗證打包邏輯
# ------------------------------------------------------------------
if __name__ == "__main__":
    # 檢查一：0 指令應該落在每個範圍的中點附近
    print("零指令 :", pack_mit_command(0, 0, 0, 0, 0).hex(" "))
    print("5 N·m  :", pack_mit_command(0, 0, 0, 0, 5.0).hex(" "))
    print("-5 N·m :", pack_mit_command(0, 0, 0, 0, -5.0).hex(" "))

    # 檢查二：來回轉換誤差應該小於一個量化刻度
    for t in (-65, -20, 0, 12.34, 65):
        i = float_to_uint(t, T_MIN, T_MAX, 12)
        back = uint_to_float(i, T_MIN, T_MAX, 12)
        print(f"扭力 {t:+7.2f} → int {i:4d} → {back:+7.3f}  誤差 {back - t:+.4f}")

    print(f"\n扭力量化解析度 = {(T_MAX - T_MIN) / 4096:.4f} N·m")
    print("→ 掃描實驗的步階不要小於這個值")
