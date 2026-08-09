from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from ..experiment_specs import validate_request
from ..workers import ConnectionTestWorker, ExperimentWorker


class ExperimentController(QObject):
    running_changed = Signal(bool)

    def __init__(self, *, parent, state, hardware_panel, experiment_panel, telemetry_panel):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.hardware_panel = hardware_panel
        self.experiment_panel = experiment_panel
        self.telemetry_panel = telemetry_panel
        self.worker = None
        self.test_worker = None
        self.background_busy_check = None
        experiment_panel.start_requested.connect(self.start)
        experiment_panel.stop_requested.connect(self.stop)
        hardware_panel.test_requested.connect(self.test_connections)

    def _hardware(self):
        values = self.hardware_panel.settings()
        for key, value in values.items():
            setattr(self.state.hardware, key, value)
        return values

    def _set_running(self, running):
        self.hardware_panel.set_running(running)
        self.experiment_panel.set_running(running)
        self.running_changed.emit(running)

    def _status(self, message):
        self.parent_window.statusBar().showMessage(message, 15000)

    def start(self, kind, params):
        if self.is_running():
            return
        if self.background_busy_check and self.background_busy_check():
            QMessageBox.warning(self.parent_window, "裝置忙碌", "請先結束 Manual Control。")
            return
        try:
            hardware = self._hardware()
            validate_request(kind, params, hardware)
        except Exception as exc:
            QMessageBox.warning(self.parent_window, "設定錯誤", str(exc))
            return
        answer = QMessageBox.question(
            self.parent_window,
            "開始 Motor Feedback Check",
            "請確認馬達固定妥當、活動範圍無障礙，且 Hardware E-Stop 可立即使用。\n"
            "Software Stop 並不是 Hardware E-Stop。是否繼續？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.telemetry_panel.reset()
        self.worker = ExperimentWorker(kind, params, hardware, self)
        self.worker.status.connect(self._status)
        self.worker.progress.connect(self.experiment_panel.set_progress)
        self.worker.telemetry.connect(self.telemetry_panel.update_telemetry)
        self.worker.action_required.connect(self._handle_action)
        self.worker.completed.connect(self._experiment_completed)
        self.worker.finished.connect(self._worker_finished)
        self._set_running(True)
        self.worker.start()

    def _handle_action(self, title, text):
        if self.worker is None:
            return
        answer = QMessageBox.question(
            self.parent_window, title, text,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort,
            QMessageBox.StandardButton.Ok,
        )
        if answer == QMessageBox.StandardButton.Ok:
            self.worker.continue_action()
        else:
            self.stop()

    def stop(self):
        if self.worker is not None and self.worker.isRunning():
            self._status("Software Stop requested; commanding Motor Idle.")
            self.worker.request_stop()
        if self.test_worker is not None and self.test_worker.isRunning():
            self.test_worker.request_stop()

    def _experiment_completed(self, ok, message):
        self._set_running(False)
        self._status(message)
        dialog = QMessageBox.information if ok else QMessageBox.warning
        dialog(self.parent_window, "Motor Feedback Check", message)

    def _worker_finished(self):
        worker = self.sender()
        if worker is self.worker:
            self.worker = None
        worker.deleteLater()

    def test_connections(self):
        if self.is_running():
            return
        if self.background_busy_check and self.background_busy_check():
            QMessageBox.warning(self.parent_window, "裝置忙碌", "請先結束 Manual Control。")
            return
        try:
            hardware = self._hardware()
            validate_request("verify", {"velocity": 0.1, "duration_s": 0.5}, hardware)
        except Exception as exc:
            QMessageBox.warning(self.parent_window, "設定錯誤", str(exc))
            return
        self._set_running(True)
        self.hardware_panel.set_connection_status("測試中…")
        self.test_worker = ConnectionTestWorker(hardware, self)
        self.test_worker.status.connect(self._status)
        self.test_worker.completed.connect(self._test_completed)
        self.test_worker.finished.connect(self._test_finished)
        self.test_worker.start()

    def _test_completed(self, ok, message):
        self._set_running(False)
        self.hardware_panel.set_connection_status("連線正常" if ok else "連線失敗", ok)
        self._status(message)
        dialog = QMessageBox.information if ok else QMessageBox.warning
        dialog(self.parent_window, "Motor Backend 測試", message)

    def _test_finished(self):
        worker = self.sender()
        if worker is self.test_worker:
            self.test_worker = None
        worker.deleteLater()

    def is_running(self):
        return bool((self.worker and self.worker.isRunning()) or
                    (self.test_worker and self.test_worker.isRunning()))

    def stop_and_wait(self, timeout_ms=4000):
        self.stop()
        workers = [w for w in (self.worker, self.test_worker) if w is not None]
        return all(not w.isRunning() or w.wait(timeout_ms) for w in workers)

    def set_background_busy_check(self, callback):
        self.background_busy_check = callback
