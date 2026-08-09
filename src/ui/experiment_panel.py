from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..experiment_specs import EXPERIMENT_HELP
from .spin_boxes import StepDoubleSpinBox


class ExperimentPanel(QWidget):
    start_requested = Signal(str, dict)
    stop_requested = Signal()

    def __init__(self, _safe_torque_default=None, parent=None):
        super().__init__(parent)
        self._running = False
        title = QLabel("Motor Feedback / Scaling Check")
        title.setStyleSheet("font-size:14pt; font-weight:600;")
        help_label = QLabel(EXPERIMENT_HELP["verify"])
        help_label.setWordWrap(True)
        self.velocity = self._double(2.0, -10.0, 10.0, " rad/s")
        self.duration = self._double(3.0, 1.0, 30.0, " s")
        form = QFormLayout()
        form.addRow("測試速度", self.velocity)
        form.addRow("持續時間", self.duration)
        self.acks = [
            QCheckBox("馬達已固定，活動範圍內沒有障礙物"),
            QCheckBox("Hardware E-Stop 已確認可立即使用"),
        ]
        for check in self.acks:
            check.toggled.connect(self._update_start_enabled)
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.phase_label = QLabel("就緒")
        self.start_button = QPushButton("開始 Motor Feedback Check")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._emit_start)
        self.stop_button = QPushButton("Software Stop / Motor Idle")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.clicked.connect(self.stop_requested)
        self.stop_button.setEnabled(False)
        warning = QLabel("Software Stop 並不是 Hardware E-Stop")
        warning.setStyleSheet("color:#b91c1c; font-weight:600;")
        buttons = QHBoxLayout(); buttons.addWidget(self.start_button); buttons.addWidget(self.stop_button)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(title); layout.addWidget(help_label); layout.addLayout(form)
        for check in self.acks: layout.addWidget(check)
        layout.addWidget(self.progress); layout.addWidget(self.phase_label); layout.addWidget(warning)
        layout.addLayout(buttons); layout.addStretch(1)
        self._update_start_enabled()

    @staticmethod
    def _double(value, minimum, maximum, suffix):
        widget = StepDoubleSpinBox(); widget.setRange(minimum, maximum)
        widget.setDecimals(3); widget.setValue(value); widget.setSuffix(suffix)
        return widget

    def _emit_start(self):
        self.start_requested.emit("verify", {"velocity_rads": self.velocity.value(), "spin_duration_s": self.duration.value()})

    def _update_start_enabled(self):
        self.start_button.setEnabled(not self._running and all(check.isChecked() for check in self.acks))

    def set_running(self, running):
        self._running = running
        self.velocity.setEnabled(not running); self.duration.setEnabled(not running)
        for check in self.acks: check.setEnabled(not running)
        self.stop_button.setEnabled(running); self._update_start_enabled()
        if running: self.progress.setValue(0)

    def set_progress(self, value, phase):
        self.progress.setValue(value); self.phase_label.setText(phase)
