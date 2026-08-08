from contextlib import redirect_stdout, redirect_stderr
import importlib
import os
from pathlib import Path
import subprocess
import sys
import threading

from PySide6.QtCore import QThread, Signal

from ..runtime import application_root


PROJECT_ROOT = application_root()


class _SignalStream:
    def __init__(self, signal):
        self.signal = signal
        self.pending = ""

    def write(self, text):
        self.pending += str(text)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if line:
                self.signal.emit(line)
        return len(text)

    def flush(self):
        if self.pending:
            self.signal.emit(self.pending)
            self.pending = ""


class ProcessWorker(QThread):
    output = Signal(str)
    completed = Signal(bool, str, list)

    def __init__(self, mode, input_path="", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.input_path = input_path
        self._stop = threading.Event()
        self._process = None

    def request_stop(self):
        self._stop.set()
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        if getattr(sys, "frozen", False):
            self._run_frozen()
            return

        if self.mode == "analyze":
            args = [sys.executable, str(PROJECT_ROOT / "analyze.py"), self.input_path]
        elif self.mode == "simulate":
            args = [sys.executable, str(PROJECT_ROOT / "simulate.py")]
        else:
            self.completed.emit(False, f"未知工作：{self.mode}", [])
            return

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["MPLBACKEND"] = "Agg"
        try:
            self._process = subprocess.Popen(
                args,
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert self._process.stdout is not None
            for line in self._process.stdout:
                self.output.emit(line.rstrip())
                if self._stop.is_set():
                    break
            code = self._process.wait()
            if self._stop.is_set():
                self.completed.emit(False, "工作已取消", [])
                return
            if code != 0:
                self.completed.emit(False, f"處理程序結束碼：{code}", [])
                return
            if self.mode == "analyze":
                stem = Path(self.input_path).stem
                output_dir = PROJECT_ROOT / "data" / "analysis"
                images = sorted(str(path) for path in output_dir.glob(f"{stem}_*.png"))
                self.completed.emit(True, "分析完成", images)
            else:
                self.completed.emit(True, "模擬資料產生完成", [])
        except Exception as exc:
            self.completed.emit(False, f"工作失敗：{exc}", [])
        finally:
            self._process = None

    def _run_frozen(self):
        """Run bundled modules in-process because a one-file EXE has no .py children."""
        stream = _SignalStream(self.output)
        try:
            with redirect_stdout(stream), redirect_stderr(stream):
                if self.mode == "analyze":
                    import analyze

                    input_path = Path(self.input_path).resolve()
                    output_dir = input_path.parent / "analysis"
                    images = analyze.analyze_file(input_path, output_dir=output_dir)
                    stream.flush()
                    if self._stop.is_set():
                        self.completed.emit(False, "工作已取消", [])
                    else:
                        self.completed.emit(True, "分析完成", [str(path) for path in images])
                elif self.mode == "simulate":
                    previous_cwd = Path.cwd()
                    try:
                        os.chdir(PROJECT_ROOT)
                        if "simulate" in sys.modules:
                            importlib.reload(sys.modules["simulate"])
                        else:
                            import simulate  # noqa: F401 - importing generates the data files
                    finally:
                        os.chdir(previous_cwd)
                    stream.flush()
                    if self._stop.is_set():
                        self.completed.emit(False, "工作已取消", [])
                    else:
                        self.completed.emit(True, "模擬資料產生完成", [])
                else:
                    self.completed.emit(False, f"未知工作：{self.mode}", [])
        except Exception as exc:
            stream.flush()
            self.completed.emit(False, f"工作失敗：{exc}", [])
