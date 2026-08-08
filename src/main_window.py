from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMainWindow, QMessageBox

from .app_state import AppState
from .application import ApplicationComposer


class MainWindow(QMainWindow):
    def __init__(self, state=None):
        super().__init__()
        self.state = state or AppState()
        self.setWindowTitle("AK10-9 V3.0 馬達特性化測試台")
        self.resize(1440, 880)
        self.setMinimumSize(1120, 700)
        self.components = ApplicationComposer(self, self.state).compose()
        self.setCentralWidget(self.components.workspace)
        self._build_menu()
        self.statusBar().showMessage("待命；開始前請先完成硬體連線測試與安全確認。")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("檔案")
        analyze_action = QAction("選擇 CSV 並分析…", self)
        analyze_action.triggered.connect(self._choose_analysis_file)
        file_menu.addAction(analyze_action)
        open_data_action = QAction("開啟資料目錄", self)
        open_data_action.triggered.connect(self._open_data_dir)
        file_menu.addAction(open_data_action)
        file_menu.addSeparator()
        exit_action = QAction("離開", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = self.menuBar().addMenu("工具")
        simulate_action = QAction("產生模擬資料", self)
        simulate_action.triggered.connect(self.components.analysis_controller.simulate)
        tools_menu.addAction(simulate_action)
        test_action = QAction("測試硬體連線", self)
        test_action.triggered.connect(self.components.experiment_controller.test_connections)
        tools_menu.addAction(test_action)

        help_menu = self.menuBar().addMenu("說明")
        about_action = QAction("關於與安全提醒", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    def _choose_analysis_file(self):
        path = self.components.analysis_panel.choose_file()
        if path:
            self.components.analysis_controller.analyze(path)

    def _open_data_dir(self):
        path = Path(self.components.hardware_panel.settings()["log_dir"])
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _about(self):
        QMessageBox.information(
            self,
            "AK10-9 馬達特性化測試台",
            "本 GUI 涵蓋 README 中的縮放驗證、Kt、正反向、反驅、熱衰減、"
            "模擬資料及離線分析。\n\n"
            "警告：軟體安全上限與停止按鈕不能取代機械限位、實體 E-stop 與電源開關。",
        )

    def closeEvent(self, event):
        experiment = self.components.experiment_controller
        analysis = self.components.analysis_controller
        if experiment.is_running():
            answer = QMessageBox.question(
                self,
                "實驗仍在執行",
                "關閉程式會先將馬達切回 idle 並停止記錄。確定要關閉？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if not experiment.stop_and_wait() or not analysis.stop_and_wait():
            QMessageBox.warning(self, "背景工作尚未結束", "請稍候片刻後再關閉程式。")
            event.ignore()
            return
        event.accept()
