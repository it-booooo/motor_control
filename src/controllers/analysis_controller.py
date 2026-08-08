from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from ..workers import ProcessWorker


class AnalysisController(QObject):
    running_changed = Signal(bool)

    def __init__(self, *, parent, panel):
        super().__init__(parent)
        self.parent_window = parent
        self.panel = panel
        self.worker = None
        self.measurement_busy_check = None
        panel.analyze_requested.connect(self.analyze)
        panel.simulate_requested.connect(self.simulate)
        panel.stop_requested.connect(self.stop)

    def analyze(self, path):
        if self.is_running():
            return
        if self.measurement_busy_check and self.measurement_busy_check():
            QMessageBox.warning(self.parent_window, "量測進行中", "量測期間不執行離線分析，以免影響記錄時序。")
            return
        csv_path = Path(path)
        if not csv_path.is_file():
            QMessageBox.warning(self.parent_window, "無法分析", "請先選擇存在的 CSV 檔案。")
            return
        self.panel.set_file(str(csv_path.resolve()))
        self.panel.clear_log()
        self.panel.set_images([])
        self._start(ProcessWorker("analyze", str(csv_path.resolve()), self))

    def simulate(self):
        if self.is_running():
            return
        if self.measurement_busy_check and self.measurement_busy_check():
            QMessageBox.warning(self.parent_window, "量測進行中", "量測期間不產生模擬資料，以免影響記錄時序。")
            return
        self.panel.clear_log()
        self.panel.set_images([])
        self._start(ProcessWorker("simulate", parent=self))

    def _start(self, worker):
        self.worker = worker
        worker.output.connect(self.panel.append_log)
        worker.completed.connect(self._completed)
        worker.finished.connect(self._worker_finished)
        self.panel.set_busy(True)
        self.running_changed.emit(True)
        worker.start()

    def _completed(self, ok, message, images):
        self.panel.set_busy(False)
        self.running_changed.emit(False)
        self.panel.append_log(message)
        self.parent_window.statusBar().showMessage(message, 15000)
        if ok:
            self.panel.set_images(images)
            if self.worker is not None and self.worker.mode == "simulate":
                from ..runtime import application_root

                default = application_root() / "data" / "sim_kt_calib.csv"
                self.panel.set_file(str(default))
        else:
            QMessageBox.warning(self.parent_window, "處理未完成", message)

    def _worker_finished(self):
        worker = self.sender()
        if worker is self.worker:
            self.worker = None
        worker.deleteLater()

    def stop(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()

    def is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def stop_and_wait(self, timeout_ms=4000):
        self.stop()
        return self.worker is None or not self.worker.isRunning() or self.worker.wait(timeout_ms)

    def set_measurement_busy_check(self, callback):
        self.measurement_busy_check = callback
