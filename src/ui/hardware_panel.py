from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .spin_boxes import StepDoubleSpinBox, StepSpinBox


class HardwarePanel(QWidget):
    test_requested = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state

        self.can_interface = QComboBox()
        self.can_interface.setEditable(True)
        self.can_interface.addItems(["socketcan", "pcan", "slcan", "virtual"])
        self.can_interface.setCurrentText(state.can_interface)
        self.can_channel = QLineEdit(state.can_channel)
        self.can_bitrate = self._int_spin(10_000, 10_000_000, state.can_bitrate)
        self.motor_id = self._int_spin(0, 255, state.motor_id)
        self.command_rate = self._int_spin(1, 2000, state.command_rate_hz)

        self.loadcell_port = QComboBox()
        self.loadcell_port.setEditable(True)
        self.refresh_ports(state.loadcell_port)
        self.loadcell_baud = self._int_spin(1200, 3_000_000, state.loadcell_baud)
        self.loadcell_sign = QComboBox()
        self.loadcell_sign.addItem("+1（壓力為正）", 1.0)
        self.loadcell_sign.addItem("-1（反轉方向）", -1.0)
        self.loadcell_sign.setCurrentIndex(0 if state.loadcell_sign >= 0 else 1)

        self.lever = self._double_spin(0.001, 2.0, state.lever_m, 4, " m")
        self.safe_torque = self._double_spin(0.01, 65.0, state.safe_torque_max, 2, " N·m")
        self.safe_current = self._double_spin(0.01, 100.0, state.safe_current_a, 2, " A")
        self.safe_temp = self._double_spin(1.0, 150.0, state.safe_temp_c, 1, " °C")
        self.log_rate = self._int_spin(1, 2000, state.log_rate_hz)
        self.log_dir = QLineEdit(state.log_dir)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("CAN 介面", self.can_interface)
        form.addRow("CAN 通道", self.can_channel)
        form.addRow("CAN bitrate", self.can_bitrate)
        form.addRow("馬達 ID", self.motor_id)
        form.addRow("指令頻率", self.command_rate)
        form.addRow("Load cell 埠", self._with_button(self.loadcell_port, "重新掃描", self.refresh_ports))
        form.addRow("Load cell baud", self.loadcell_baud)
        form.addRow("Load cell 方向", self.loadcell_sign)
        form.addRow("力臂長度", self.lever)
        form.addRow("安全扭力", self.safe_torque)
        form.addRow("安全電流", self.safe_current)
        form.addRow("安全溫度", self.safe_temp)
        form.addRow("記錄頻率", self.log_rate)
        form.addRow("資料目錄", self._with_button(self.log_dir, "選擇…", self.choose_log_dir))

        self.test_button = QPushButton("測試 CAN 與 Load cell")
        self.test_button.clicked.connect(self.test_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addWidget(self.test_button)

    @staticmethod
    def _int_spin(minimum, maximum, value):
        widget = StepSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setGroupSeparatorShown(True)
        return widget

    @staticmethod
    def _double_spin(minimum, maximum, value, decimals, suffix):
        widget = StepDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    @staticmethod
    def _with_button(widget, text, callback):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(widget, 1)
        button = QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return container

    def refresh_ports(self, preferred=None):
        current = preferred or self.loadcell_port.currentText()
        try:
            from serial.tools import list_ports

            ports = [port.device for port in list_ports.comports()]
        except Exception:
            ports = []
        self.loadcell_port.clear()
        self.loadcell_port.addItems(ports)
        self.loadcell_port.setCurrentText(current)

    def choose_log_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "選擇資料目錄", self.log_dir.text() or str(Path.cwd())
        )
        if path:
            self.log_dir.setText(path)

    def settings(self):
        path = str(Path(self.log_dir.text().strip()).expanduser().resolve())
        return {
            "can_interface": self.can_interface.currentText().strip(),
            "can_channel": self.can_channel.text().strip(),
            "can_bitrate": self.can_bitrate.value(),
            "motor_id": self.motor_id.value(),
            "command_rate_hz": self.command_rate.value(),
            "loadcell_port": self.loadcell_port.currentText().strip(),
            "loadcell_baud": self.loadcell_baud.value(),
            "loadcell_sign": self.loadcell_sign.currentData(),
            "lever_m": self.lever.value(),
            "safe_torque_max": self.safe_torque.value(),
            "safe_current_a": self.safe_current.value(),
            "safe_temp_c": self.safe_temp.value(),
            "log_rate_hz": self.log_rate.value(),
            "log_dir": path,
        }

    def set_running(self, running):
        self.setEnabled(not running)
