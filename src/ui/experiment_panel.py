from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..experiment_specs import EXPERIMENT_HELP, EXPERIMENT_LABELS
from .spin_boxes import StepDoubleSpinBox, StepSpinBox


class ExperimentPanel(QWidget):
    start_requested = Signal(str, dict, bool)
    stop_requested = Signal()

    def __init__(self, safe_torque_default, parent=None):
        super().__init__(parent)
        self._running = False
        self.selector = QComboBox()
        for key, label in EXPERIMENT_LABELS.items():
            self.selector.addItem(label, key)
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("color:#475569; padding:4px 0;")

        self.pages = QStackedWidget()
        self.inputs = {}
        self._add_verify_page()
        self._add_kt_page(safe_torque_default)
        self._add_asym_page(safe_torque_default)
        self._add_backdrive_page()
        self._add_thermal_page(safe_torque_default)
        self.selector.currentIndexChanged.connect(self._selection_changed)

        self.acks = [
            QCheckBox("治具已鎖固，力臂兩側已有機械限位"),
            QCheckBox("實體電源／E-stop 在伸手可及處"),
            QCheckBox("旋轉範圍已清空，現場人員已知悉"),
        ]
        for check in self.acks:
            check.toggled.connect(self._update_start_enabled)

        self.auto_analyze = QCheckBox("量測完成後自動分析")
        self.auto_analyze.setChecked(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.phase_label = QLabel("待命")

        self.start_button = QPushButton("開始實驗")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._emit_start)
        self.stop_button = QPushButton("緊急停止 / Motor Idle")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.selector)
        layout.addWidget(self.help_label)
        layout.addWidget(self.pages)
        for check in self.acks:
            layout.addWidget(check)
        layout.addWidget(self.auto_analyze)
        layout.addWidget(self.progress)
        layout.addWidget(self.phase_label)
        layout.addLayout(buttons)
        self._selection_changed(0)
        self._update_start_enabled()

    @staticmethod
    def _double(value, minimum=0.01, maximum=3600.0, suffix=" s", decimals=2):
        widget = StepDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    @staticmethod
    def _integer(value, minimum=1, maximum=1000):
        widget = StepSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        return widget

    def _page(self, rows):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 3, 0, 3)
        for label, widget in rows:
            form.addRow(label, widget)
        self.pages.addWidget(page)

    def _add_verify_page(self):
        velocity = self._double(2.0, 0.1, 10.0, " rad/s")
        duration = self._double(3.0, 1.0, 30.0)
        self.inputs["verify"] = {"velocity_rads": velocity, "spin_duration_s": duration}
        self._page([("測試速度", velocity), ("取樣時間", duration)])

    def _add_kt_page(self, safe):
        torque = self._double(safe, 0.01, 65.0, " N·m")
        steps = self._integer(10, 3, 100)
        hold = self._double(3.0)
        rest = self._double(5.0)
        self.inputs["kt"] = {"torque_max": torque, "steps": steps, "hold_s": hold, "rest_s": rest}
        self._page([("最大扭力", torque), ("階數", steps), ("每階保持", hold), ("階間休息", rest)])

    def _add_asym_page(self, safe):
        torque = self._double(safe, 0.01, 65.0, " N·m")
        steps = self._integer(8, 1, 100)
        hold = self._double(3.0)
        rest = self._double(4.0)
        self.inputs["asym"] = {"torque_max": torque, "steps": steps, "hold_s": hold, "rest_s": rest}
        self._page([("最大 |扭力|", torque), ("每方向階數", steps), ("每階保持", hold), ("階間休息", rest)])

    def _add_backdrive_page(self):
        duration = self._double(60.0, 1.0, 3600.0)
        self.inputs["backdrive"] = {"duration_s": duration}
        self._page([("記錄時間", duration)])

    def _add_thermal_page(self, safe):
        torque = self._double(safe * 0.5, -65.0, 65.0, " N·m")
        duration = self._double(600.0, 1.0, 86400.0)
        cooldown = self._double(300.0, 0.0, 86400.0)
        mount = QComboBox()
        mount.setEditable(True)
        mount.addItems(["stock", "pla", "alu", "alu_fin", "alu_paste"])
        self.inputs["thermal"] = {
            "torque": torque,
            "duration_s": duration,
            "cooldown_s": cooldown,
            "mount_label": mount,
        }
        self._page([("固定扭力", torque), ("升溫記錄", duration), ("降溫記錄", cooldown), ("固定座標籤", mount)])

    def _selection_changed(self, index):
        self.pages.setCurrentIndex(index)
        kind = self.selector.itemData(index)
        self.help_label.setText(EXPERIMENT_HELP[kind])

    def _update_start_enabled(self):
        self.start_button.setEnabled(
            not self._running and all(check.isChecked() for check in self.acks)
        )

    def _values(self, kind):
        result = {}
        for key, widget in self.inputs[kind].items():
            if isinstance(widget, StepSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, StepDoubleSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText().strip()
        return result

    def _emit_start(self):
        kind = self.selector.currentData()
        self.start_requested.emit(kind, self._values(kind), self.auto_analyze.isChecked())

    def set_running(self, running):
        self._running = running
        self.selector.setEnabled(not running)
        self.pages.setEnabled(not running)
        for check in self.acks:
            check.setEnabled(not running)
        self._update_start_enabled()
        self.stop_button.setEnabled(running)
        if running:
            self.progress.setValue(0)

    def set_progress(self, value, phase):
        self.progress.setValue(value)
        self.phase_label.setText(phase)
