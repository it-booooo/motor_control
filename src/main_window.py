from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox

from .app_state import AppState
from .application import ApplicationComposer


class MainWindow(QMainWindow):
    def __init__(self, state=None):
        super().__init__()
        self.state = state or AppState()
        self.setWindowTitle("Motor Communication Console")
        self.resize(1440, 820)
        self.setMinimumSize(1120, 680)
        self.components = ApplicationComposer(self, self.state).compose()
        self.setCentralWidget(self.components.workspace)
        self._build_menu()
        self.statusBar().showMessage("就緒：請設定 Motor Backend 後測試連線。")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("檔案")
        exit_action = QAction("離開", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        tools_menu = self.menuBar().addMenu("工具")
        test_action = QAction("測試 Motor Backend", self)
        test_action.triggered.connect(self.components.experiment_controller.test_connections)
        tools_menu.addAction(test_action)
        help_menu = self.menuBar().addMenu("說明")
        about_action = QAction("關於", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    def _about(self):
        QMessageBox.information(
            self, "Motor Communication Console",
            "此工具只處理電腦、STM32/CAN 與馬達之間的命令與回授。\n"
            "Software Stop 並不是 Hardware E-Stop。",
        )

    def closeEvent(self, event):
        experiment = self.components.experiment_controller
        manual = self.components.manual_control_controller
        if experiment.is_running() or manual.is_running():
            answer = QMessageBox.question(
                self, "通訊仍在執行",
                "關閉前將要求 Motor Idle 並中止通訊。是否繼續？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if not experiment.stop_and_wait() or not manual.stop_and_wait():
            QMessageBox.warning(self, "無法安全關閉", "背景通訊尚未停止，請使用 Hardware E-Stop 並確認設備狀態。")
            event.ignore()
            return
        event.accept()
