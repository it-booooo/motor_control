import math
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal

from ak_can import AKMotor, ERROR_TEXT
from config import GEAR_RATIO, POLE_PAIRS
from loadcell import LoadCell
from logger import RateLimiter, Recorder, SafetyTripped

from ..experiment_specs import estimated_duration


class ExperimentCancelled(Exception):
    pass


class ConnectionTestWorker(QThread):
    status = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, hardware, parent=None):
        super().__init__(parent)
        self.hardware = hardware
        self._stop = threading.Event()

    def request_stop(self):
        self._stop.set()

    def run(self):
        motor = None
        loadcell = None
        try:
            self.status.emit("正在開啟 CAN…")
            motor = _make_motor(self.hardware)
            motor.open()
            deadline = time.perf_counter() + 3.0
            while motor.read() is None and time.perf_counter() < deadline:
                if self._stop.wait(0.05):
                    raise ExperimentCancelled()
            state = motor.read()
            if state is None:
                raise RuntimeError("CAN 已開啟，但 3 秒內沒有收到馬達回授")
            self.status.emit(
                f"CAN 正常：位置 {state.pos_deg:.1f}°，溫度 {state.temp_c:.1f}°C"
            )
            motor.close()
            motor = None

            if self._stop.is_set():
                raise ExperimentCancelled()
            self.status.emit("正在開啟 load cell…")
            loadcell = _make_loadcell(self.hardware)
            loadcell.open()
            sample = loadcell.read()
            if sample is None:
                raise RuntimeError("load cell 已開啟，但沒有收到資料")
            self.status.emit(
                f"Load cell 正常：{sample.grams:+.1f} g / {sample.newton:+.3f} N"
            )
            self.completed.emit(True, "CAN 與 load cell 連線測試通過")
        except ExperimentCancelled:
            self.completed.emit(False, "連線測試已取消")
        except Exception as exc:
            self.completed.emit(False, f"連線測試失敗：{exc}")
        finally:
            if motor is not None:
                try:
                    motor.close()
                except Exception:
                    pass
            if loadcell is not None:
                try:
                    loadcell.close()
                except Exception:
                    pass


class ExperimentWorker(QThread):
    status = Signal(str)
    progress = Signal(int, str)
    telemetry = Signal(dict)
    action_required = Signal(str, str)
    completed = Signal(str, bool, str)

    def __init__(self, kind, params, hardware, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.params = params
        self.hardware = hardware
        self._stop = threading.Event()
        self._prompt = threading.Event()
        self._motor = None
        self._total_seconds = estimated_duration(kind, params)
        self._completed_seconds = 0.0
        self._last_progress = -1

    def request_stop(self):
        self._stop.set()
        self._prompt.set()
        if self._motor is not None:
            self._motor.idle()

    def continue_action(self):
        self._prompt.set()

    def _check_cancel(self):
        if self._stop.is_set():
            raise ExperimentCancelled()

    def _ask(self, title, text):
        self._prompt.clear()
        self.action_required.emit(title, text)
        while not self._prompt.wait(0.1):
            self._check_cancel()
        self._check_cancel()

    def _check_safety(self, state, force=None):
        if state is None:
            raise SafetyTripped("CAN 回授中斷")
        now = time.perf_counter()
        if now - state.t > 0.25:
            raise SafetyTripped(f"CAN 回授已中斷 {now - state.t:.2f} 秒")
        if force is not None and now - force.t > 0.25:
            raise SafetyTripped(f"Load cell 資料已中斷 {now - force.t:.2f} 秒")
        if state.error:
            raise SafetyTripped(
                f"馬達錯誤 {state.error}: {ERROR_TEXT.get(state.error, '未知錯誤')}"
            )
        if state.temp_c > self.hardware["safe_temp_c"]:
            raise SafetyTripped(
                f"驅動板溫度 {state.temp_c:.1f}°C 超過 "
                f"{self.hardware['safe_temp_c']:.1f}°C"
            )
        if abs(state.current_a) > self.hardware["safe_current_a"]:
            raise SafetyTripped(
                f"電流 {state.current_a:.2f} A 超過 "
                f"{self.hardware['safe_current_a']:.2f} A"
            )

    def _emit_sample(self, state, force, phase, cmd_torque=0.0):
        if state is None and force is None:
            return
        payload = {"phase": phase, "cmd_torque": cmd_torque}
        if state is not None:
            payload.update(
                position=state.pos_deg,
                speed=state.spd_rads,
                current=state.current_a,
                temperature=state.temp_c,
                error=state.error,
            )
        if force is not None:
            payload.update(
                force=force.newton,
                torque=force.newton * self.hardware["lever_m"],
            )
        self.telemetry.emit(payload)

    def _update_progress(self, phase, elapsed=0.0):
        value = min(99, int(
            (self._completed_seconds + elapsed) / max(self._total_seconds, 0.01) * 100
        ))
        if value != self._last_progress:
            self._last_progress = value
            self.progress.emit(value, phase)

    def _hold(self, rec, loadcell, phase, seconds, cmd_torque=0.0,
              cmd_velocity=0.0):
        limiter = RateLimiter(self.hardware["log_rate_hz"])
        started = time.perf_counter()
        emit_every = max(1, int(self.hardware["log_rate_hz"] / 20))
        sample_n = 0
        while True:
            self._check_cancel()
            elapsed = time.perf_counter() - started
            if elapsed >= seconds:
                break
            state, force = rec.snapshot(
                self._motor, loadcell, phase, cmd_torque, cmd_velocity
            )
            if force is None:
                raise SafetyTripped("Load cell 資料中斷")
            self._check_safety(state, force)
            if sample_n % emit_every == 0:
                self._emit_sample(state, force, phase, cmd_torque)
                self._update_progress(phase, elapsed)
            sample_n += 1
            limiter.wait()
        self._completed_seconds += seconds
        self._update_progress(phase)

    def _wait_feedback(self, timeout=3.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self._check_cancel()
            state = self._motor.read()
            if state is not None:
                return state
            time.sleep(0.03)
        raise RuntimeError("CAN 已開啟，但沒有收到馬達回授")

    def _run_verify(self):
        self._motor.idle()
        time.sleep(0.5)
        first = self._wait_feedback()
        self._emit_sample(first, None, "verify_position")
        self._ask(
            "位置回授驗證",
            f"目前位置為 {first.pos_deg:.2f}°。\n\n"
            "請用量角器或直角尺把輸出軸手動轉動約 +90°，完成後按「繼續」。",
        )
        second = self._wait_feedback()
        delta = second.pos_deg - first.pos_deg
        self.status.emit(
            f"位置變化 {delta:+.2f}°：接近 90° 表示輸出軸角度；"
            f"接近 {90 * GEAR_RATIO:.0f}° 表示仍需除以減速比。"
        )
        self._ask(
            "速度換算驗證",
            "請拆下力臂並確認輸出軸可以自由旋轉，完成後按「繼續」。\n\n"
            "馬達會以低速旋轉，請把手與工具移出旋轉範圍。",
        )
        velocity = float(self.params["velocity_rads"])
        duration = float(self.params["spin_duration_s"])
        self._motor.velocity(velocity, kd=2.0)
        samples = []
        started = time.perf_counter()
        limiter = RateLimiter(200)
        while time.perf_counter() - started < duration:
            self._check_cancel()
            state = self._motor.read()
            self._check_safety(state)
            if state is not None:
                samples.append((state.t, state.pos_deg, state.spd_rads))
                self._emit_sample(state, None, "verify_speed")
            self._update_progress("verify_speed", time.perf_counter() - started)
            limiter.wait()
        self._motor.idle()
        if len(samples) < 20:
            raise RuntimeError("速度驗證樣本少於 20 筆，請檢查 CAN 回授頻率")
        t0, p0, _ = samples[0]
        t1, p1, _ = samples[-1]
        from_position = math.radians(p1 - p0) / max(t1 - t0, 1e-9)
        from_erpm = sum(row[2] for row in samples) / len(samples)
        ratio = from_position / from_erpm if abs(from_erpm) > 1e-9 else float("nan")
        suggested = POLE_PAIRS / ratio if ratio and math.isfinite(ratio) else float("nan")
        self.status.emit(
            f"位置微分速度 {from_position:+.4f} rad/s；eRPM 換算 "
            f"{from_erpm:+.4f} rad/s；比值 {ratio:.4f}；"
            f"建議 POLE_PAIRS 約 {suggested:.1f}（目前 {POLE_PAIRS}）。"
        )

    def _run_kt(self, rec, loadcell):
        p = self.params
        steps = [p["torque_max"] * (i + 1) / p["steps"] for i in range(p["steps"])]
        self._hold(rec, loadcell, "zero", 2.0)
        for torque in steps:
            self.status.emit(f"Kt 掃描：指令 {torque:.2f} N·m")
            self._motor.torque(torque)
            self._hold(rec, loadcell, f"step_{torque:.2f}", p["hold_s"], torque)
            self._motor.idle()
            self._hold(rec, loadcell, "rest", p["rest_s"])

    def _run_asym(self, rec, loadcell):
        p = self.params
        for i in range(p["steps"]):
            magnitude = p["torque_max"] * (i + 1) / p["steps"]
            for sign in (1, -1):
                torque = sign * magnitude
                self.status.emit(f"正反向掃描：指令 {torque:+.2f} N·m")
                self._motor.torque(torque)
                self._hold(rec, loadcell, f"dir_{torque:+.2f}", p["hold_s"], torque)
                self._motor.idle()
                self._hold(rec, loadcell, "rest", p["rest_s"])

    def _run_backdrive(self, rec, loadcell):
        self._motor.idle()
        self.status.emit("馬達已 idle，請用手緩慢來回推動力臂")
        self._hold(rec, loadcell, "backdrive", self.params["duration_s"])

    def _run_thermal(self, rec, loadcell):
        p = self.params
        self._hold(rec, loadcell, "pre", 10.0)
        self.status.emit(
            f"熱測試：固定 {p['torque']:.2f} N·m，持續 {p['duration_s'] / 60:.1f} 分鐘"
        )
        self._motor.torque(p["torque"])
        self._hold(rec, loadcell, "soak", p["duration_s"], p["torque"])
        self._motor.idle()
        self.status.emit(f"進入降溫記錄 {p['cooldown_s']:.0f} 秒")
        self._hold(rec, loadcell, "cooldown", p["cooldown_s"])

    def run(self):
        loadcell = None
        recorder = None
        data_path = ""
        cancelled = False
        message = "實驗完成"
        try:
            self.status.emit("正在開啟 CAN…")
            self._motor = _make_motor(self.hardware)
            self._motor.open()
            self._wait_feedback()
            if self.kind == "verify":
                self._run_verify()
            else:
                self.status.emit("正在開啟 load cell…")
                loadcell = _make_loadcell(self.hardware)
                loadcell.open()
                self.status.emit("正在歸零 load cell（請勿碰觸治具）…")
                noise = loadcell.tare()
                self.status.emit(f"Load cell 歸零完成，雜訊峰對峰 {noise:.2f} g")
                name = {
                    "kt": "kt_calib",
                    "asym": "direction_asym",
                    "backdrive": "backdrive",
                    "thermal": f"thermal_{self.params['mount_label']}",
                }[self.kind]
                recorder = Recorder(
                    name,
                    lever_m=self.hardware["lever_m"],
                    log_dir=self.hardware["log_dir"],
                )
                data_path = str(recorder.path)
                if self.kind == "kt":
                    self._run_kt(recorder, loadcell)
                elif self.kind == "asym":
                    self._run_asym(recorder, loadcell)
                elif self.kind == "backdrive":
                    self._run_backdrive(recorder, loadcell)
                elif self.kind == "thermal":
                    self._run_thermal(recorder, loadcell)
            self.progress.emit(100, "完成")
        except ExperimentCancelled:
            cancelled = True
            message = "實驗已由使用者停止；已保留停止前的 CSV 資料"
            self.status.emit(message)
        except SafetyTripped as exc:
            cancelled = True
            message = f"安全保護已觸發：{exc}；已保留停止前的 CSV 資料"
            self.status.emit(message)
        except Exception as exc:
            cancelled = True
            message = f"實驗失敗：{exc}"
            self.status.emit(message)
            self.status.emit(traceback.format_exc())
        finally:
            if self._motor is not None:
                try:
                    self._motor.idle()
                except Exception:
                    pass
            if recorder is not None:
                try:
                    recorder.close()
                except Exception as exc:
                    self.status.emit(f"關閉 CSV 時發生錯誤：{exc}")
            if loadcell is not None:
                try:
                    loadcell.close()
                except Exception:
                    pass
            if self._motor is not None:
                try:
                    self._motor.close()
                except Exception:
                    pass
            self._motor = None
            self.completed.emit(data_path, cancelled, message)


def _make_motor(hardware):
    return AKMotor(
        motor_id=hardware["motor_id"],
        interface=hardware["can_interface"],
        channel=hardware["can_channel"],
        bitrate=hardware["can_bitrate"],
        command_rate_hz=hardware["command_rate_hz"],
    )


def _make_loadcell(hardware):
    return LoadCell(
        port=hardware["loadcell_port"],
        baud=hardware["loadcell_baud"],
        sign=hardware["loadcell_sign"],
    )
