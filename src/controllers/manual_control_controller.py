from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from ..experiment_specs import validate_hardware_settings
from ..workers.manual_control_worker import ManualControlWorker


class ManualControlController(QObject):
    running_changed = Signal(bool)

    def __init__(self, *, parent, state, hardware_panel, manual_panel, telemetry_panel):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.hardware_panel = hardware_panel
        self.panel = manual_panel
        self.telemetry_panel = telemetry_panel
        self.worker = None
        self.busy_check = None
        manual_panel.connect_requested.connect(self.connect)
        manual_panel.disconnect_requested.connect(self.disconnect)
        manual_panel.command_requested.connect(self.send_command)
        manual_panel.idle_requested.connect(self.idle)

    def _status(self, message):
        self.parent_window.statusBar().showMessage(message, 15000)

    def connect(self):
        if self.is_running():
            return
        if self.busy_check and self.busy_check():
            QMessageBox.warning(self.parent_window, "裝置忙碌", "請先結束 Motor Feedback Check。")
            return
        hardware = self.hardware_panel.settings()
        try:
            validate_hardware_settings(hardware)
        except Exception as exc:
            QMessageBox.warning(self.parent_window, "設定錯誤", str(exc))
            return
        answer = QMessageBox.question(
            self.parent_window, "啟用 Manual Control",
            "請確認 Hardware E-Stop 可用。Software Stop 並不是 Hardware E-Stop。是否連線？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for key, value in hardware.items():
            setattr(self.state.hardware, key, value)
        self.telemetry_panel.reset()
        self.worker = ManualControlWorker(hardware, self)
        self.worker.status.connect(self._status)
        self.worker.telemetry.connect(self.telemetry_panel.update_telemetry)
        self.worker.connected.connect(self._connection_changed)
        self.worker.completed.connect(self._completed)
        self.worker.finished.connect(self._finished)
        self.hardware_panel.set_running(True)
        self.running_changed.emit(True)
        self.worker.start()

    def send_command(self, values):
        if self.worker is not None:
            self.worker.request_command(values)

    def idle(self):
        if self.worker is not None:
            self.worker.request_idle()
            self._status("Software Stop requested; this is not a Hardware E-Stop.")

    def disconnect(self):
        if self.worker is not None:
            self.worker.request_stop()

    def _completed(self, message):
        self.hardware_panel.set_running(False)
        self.panel.set_connected(False, message)
        self.running_changed.emit(False)

    def _connection_changed(self, connected, message):
        self.panel.set_connected(connected, message)
        self.hardware_panel.set_connection_status("Manual Control 已連線" if connected else "未連線", connected or None)

    def _finished(self):
        worker = self.sender()
        if worker is self.worker:
            self.worker = None
        worker.deleteLater()

    def is_running(self):
        return bool(self.worker is not None and self.worker.isRunning())

    def stop_and_wait(self, timeout_ms=4000):
        self.disconnect()
        return self.worker is None or not self.worker.isRunning() or self.worker.wait(timeout_ms)

    def set_busy_check(self, callback):
        self.busy_check = callback
