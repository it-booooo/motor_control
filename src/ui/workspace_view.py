from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class WorkspaceView(QWidget):
    def __init__(self, hardware_panel, experiment_panel, telemetry_panel,
                 analysis_panel, parent=None):
        super().__init__(parent)
        setup_tabs = QTabWidget()
        setup_tabs.addTab(hardware_panel, "硬體與安全")
        setup_tabs.addTab(experiment_panel, "實驗設定")

        live_group = self._group("即時監測", telemetry_panel)
        analysis_group = self._group("資料分析與模擬", analysis_panel)
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(live_group)
        right.addWidget(analysis_group)
        right.setChildrenCollapsible(False)
        right.setSizes([390, 360])

        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(setup_tabs)
        main.addWidget(right)
        main.setChildrenCollapsible(False)
        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([390, 990])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(main)

    @staticmethod
    def _group(title, widget):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 7, 5, 5)
        layout.addWidget(widget)
        return group
