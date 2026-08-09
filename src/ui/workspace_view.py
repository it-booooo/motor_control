from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QSplitter, QTabWidget, QVBoxLayout, QWidget


class WorkspaceView(QWidget):
    def __init__(self, hardware_panel, experiment_panel, manual_control_panel,
                 telemetry_panel, parent=None):
        super().__init__(parent)
        tabs = QTabWidget()
        tabs.addTab(hardware_panel, "Motor 通訊")
        tabs.addTab(experiment_panel, "Feedback Check")
        tabs.addTab(manual_control_panel, "Manual Control")
        live_group = QGroupBox("Motor Telemetry")
        live_layout = QVBoxLayout(live_group)
        live_layout.addWidget(telemetry_panel)
        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(tabs)
        main.addWidget(live_group)
        main.setChildrenCollapsible(False)
        main.setStretchFactor(1, 1)
        main.setSizes([400, 1000])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(main)
