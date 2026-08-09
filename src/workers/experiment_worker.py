import math
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal

from ak_can import ERROR_TEXT

from ..devices import create_motor_backend
from ..motors import get_motor_profile

# Maximum feedback age tolerated during an active experiment.  This is a
# software safety timeout, not the expected CAN latency.
FEEDBACK_TIMEOUT_S = 0.25


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
        try:
            label = {
                "stm32": "STM32 backend",
                "direct_can": "Direct CAN debug backend",
                "simulation": "Simulation backend",
            }.get(self.hardware.get("backend", "direct_can"), "motor backend")
            self.status.emit(f"正在開啟 {label}…")
            motor = create_motor_backend(self.hardware)
            motor.open()
            deadline = time.perf_counter() + 3.0
            while motor.read() is None and time.perf_counter() < deadline:
                if self._stop.wait(0.05):
                    raise ExperimentCancelled()
            state = motor.read()
            if state is None:
                raise RuntimeError("Backend 已開啟，但 3 秒內沒有收到 motor telemetry")
            stats = motor.get_can_statistics()
            self.completed.emit(
                True,
                f"{label} 正常：位置 {state.pos_deg:.1f}°，"
                f"速度 {state.spd_rads:+.3f} rad/s，溫度 {state.temp_c:.1f}°C，"
                f"CAN TX/RX {stats.can_tx_count}/{stats.can_rx_count}",
            )
        except ExperimentCancelled:
            self.completed.emit(False, "Motor backend 測試已取消")
        except Exception as exc:
            self.completed.emit(False, f"Motor backend 測試失敗：{exc}")
        finally:
            if motor is not None:
                try:
                    motor.idle()
                    motor.close()
                except Exception:
                    pass


class ExperimentWorker(QThread):
    """Run blocking hardware validation away from Qt's GUI event loop.

    The worker owns one temporary backend connection and experiment timing.  It
    reports UI state through signals and always requests Motor Idle on exit;
    realtime CAN control remains the responsibility of STM32 firmware.
    """
    status = Signal(str)
    progress = Signal(int, str)
    telemetry = Signal(dict)
    action_required = Signal(str, str)
    completed = Signal(bool, str)

    def __init__(self, kind, params, hardware, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.params = params
        self.hardware = hardware
        self.profile = get_motor_profile(hardware["motor_profile"])
        self._stop = threading.Event()
        self._prompt = threading.Event()
        self._motor = None

    def request_stop(self):
        self._stop.set()
        self._prompt.set()

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

    def _wait_feedback(self, timeout=3.0):
        """Wait for initial telemetry while still honouring a Stop request."""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self._check_cancel()
            state = self._motor.read()
            if state is not None:
                return state
            time.sleep(0.03)
        raise RuntimeError("Backend 已開啟，但沒有收到 motor telemetry")

    def _check_safety(self, state):
        """Abort when feedback is stale or violates configured software limits.

        The caller's ``finally`` block requests idle after this exception.  The
        software limits complement, but cannot replace, the physical E-stop.
        """
        if state is None:
            raise RuntimeError("Motor telemetry 中斷")
        if time.perf_counter() - state.t > FEEDBACK_TIMEOUT_S:
            raise RuntimeError("Motor telemetry 已超過 250 ms 未更新")
        if state.error:
            raise RuntimeError(
                f"馬達錯誤 {state.error}: {ERROR_TEXT.get(state.error, '未知錯誤')}"
            )
        if abs(state.current_a) > self.hardware["safe_current_a"]:
            raise RuntimeError("Motor current 超過安全上限")
        if state.temp_c > self.hardware["safe_temp_c"]:
            raise RuntimeError("Motor temperature 超過安全上限")

    def _emit(self, state, phase):
        stats = self._motor.get_can_statistics()
        self.telemetry.emit(
            {
                "phase": phase,
                "backend": self._motor.backend_type.value,
                "position": state.pos_deg,
                "speed": state.spd_rads,
                "current": state.current_a,
                "temperature": state.temp_c,
                "can_tx": stats.can_tx_count,
                "can_rx": stats.can_rx_count,
                "can_errors": (stats.can_tx_error or 0) + (stats.can_rx_error or 0),
            }
        )

    def _run_verify(self):
        self._motor.idle()
        time.sleep(0.2)
        first = self._wait_feedback()
        self._emit(first, "position_check")
        self._ask(
            "位置回授檢查",
            f"目前位置 {first.pos_deg:.2f}°。請安全地轉動輸出軸約 +90°後按繼續。",
        )
        second = self._wait_feedback()
        delta = second.pos_deg - first.pos_deg
        self.status.emit(f"Motor position feedback change: {delta:+.2f}°")
        self._ask(
            "速度回授檢查",
            "確認輸出軸可自由旋轉，且人員與工具已離開旋轉範圍後按繼續。",
        )
        velocity = float(self.params["velocity_rads"])
        duration = float(self.params["spin_duration_s"])
        self._motor.velocity(velocity, kd=2.0)
        samples = []
        started = time.perf_counter()
        while time.perf_counter() - started < duration:
            self._check_cancel()
            state = self._motor.read()
            self._check_safety(state)
            samples.append((state.t, state.pos_deg, state.spd_rads))
            self._emit(state, "speed_check")
            elapsed = time.perf_counter() - started
            self.progress.emit(min(99, int(elapsed / duration * 100)), "speed_check")
            time.sleep(0.01)
        self._motor.idle()
        if len(samples) < 5:
            raise RuntimeError("Motor feedback samples are insufficient")
        t0, p0, _ = samples[0]
        t1, p1, _ = samples[-1]
        from_position = math.radians(p1 - p0) / max(t1 - t0, 1e-9)
        from_feedback = sum(row[2] for row in samples) / len(samples)
        self.status.emit(
            f"位置微分速度 {from_position:+.4f} rad/s；"
            f"motor feedback {from_feedback:+.4f} rad/s"
        )

    def run(self):
        cancelled = False
        message = "Motor feedback check 完成"
        try:
            self.status.emit("正在開啟 motor backend…")
            self._motor = create_motor_backend(self.hardware)
            self._motor.open()
            self._wait_feedback()
            self._run_verify()
            self.progress.emit(100, "完成")
        except ExperimentCancelled:
            cancelled = True
            message = "Motor feedback check 已由使用者停止"
        except Exception as exc:
            cancelled = True
            message = f"Motor feedback check 失敗：{exc}"
            self.status.emit(traceback.format_exc())
        finally:
            if self._motor is not None:
                try:
                    self._motor.idle()
                    self._motor.close()
                except Exception:
                    pass
            self._motor = None
            self.completed.emit(cancelled, message)
