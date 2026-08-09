from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..motors import MOTOR_PROFILES
from ..motors.control_modes import CONTROL_MODE_LABELS
from .spin_boxes import StepDoubleSpinBox, StepSpinBox


class HardwarePanel(QWidget):
    test_requested = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)

        self.motor_model = QComboBox()
        for profile in MOTOR_PROFILES.values():
            self.motor_model.addItem(profile.display_name, profile.key)
        self.motor_model.setCurrentIndex(
            max(0, self.motor_model.findData(state.motor_profile))
        )
        self.motor_model.currentIndexChanged.connect(self._refresh_control_modes)
        self.motor_id = self._int_spin(0, 255, state.motor_id)
        self.control_mode = QComboBox()
        self._refresh_control_modes(preferred=state.control_mode)

        self.backend = QComboBox()
        self.backend.addItem("STM32（正式）", "stm32")
        self.backend.addItem("Direct CAN（Debug）", "direct_can")
        self.backend.addItem("Simulation", "simulation")
        self.backend.setCurrentIndex(max(0, self.backend.findData(state.backend)))
        self.backend.currentIndexChanged.connect(self._update_backend_visibility)
        self.stm32_port = QComboBox()
        self.stm32_port.setEditable(True)
        self._refresh_port_combo(self.stm32_port, state.stm32_port)
        self.stm32_baud = self._int_spin(1200, 3_000_000, state.stm32_baud)
        self.connection_status = QLabel("未連線")
        self.connection_status.setStyleSheet("color:#64748b;")

        self.can_interface = QComboBox()
        self.can_interface.setEditable(True)
        self.can_interface.addItems(["socketcan", "pcan", "slcan", "virtual"])
        self.can_interface.setCurrentText(state.can_interface)
        self.can_channel = QLineEdit(state.can_channel)
        self.can_bitrate = self._int_spin(10_000, 10_000_000, state.can_bitrate)
        self.command_rate = self._int_spin(1, 2000, state.command_rate_hz)

        self.safe_torque = self._double_spin(
            0.01, 65.0, state.safe_torque_max, 2, " N·m"
        )
        self.safe_current = self._double_spin(
            0.01, 100.0, state.safe_current_a, 2, " A"
        )
        self.safe_temp = self._double_spin(
            1.0, 150.0, state.safe_temp_c, 1, " °C"
        )

        motor_group = self._section(
            "Motor",
            [
                ("Motor Model", self.motor_model),
                ("Motor ID", self.motor_id),
                ("Control Mode", self.control_mode),
            ],
        )
        self.stm32_port_row = self._with_button(
            self.stm32_port, "重新掃描", self.refresh_stm32_ports
        )
        self.stm32_baud_row = self._row_widget(self.stm32_baud)
        backend_group = self._section(
            "STM32 / Backend",
            [
                ("Backend", self.backend),
                ("STM32 Port", self.stm32_port_row),
                ("STM32 Baud", self.stm32_baud_row),
                ("Connection Status", self.connection_status),
            ],
        )
        self.direct_interface_row = self._row_widget(self.can_interface)
        self.direct_channel_row = self._row_widget(self.can_channel)
        can_group = self._section(
            "CAN",
            [
                ("Bitrate", self.can_bitrate),
                ("Command Rate", self.command_rate),
                ("CAN Interface（Debug）", self.direct_interface_row),
                ("CAN Channel（Debug）", self.direct_channel_row),
            ],
        )
        safety_group = self._section(
            "Motor Safety Limits",
            [
                ("Torque Limit", self.safe_torque),
                ("Current Limit", self.safe_current),
                ("Temperature Limit", self.safe_temp),
            ],
        )

        self.test_button = QPushButton("測試 Motor Backend")
        self.test_button.clicked.connect(self.test_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        for group in (motor_group, backend_group, can_group, safety_group):
            layout.addWidget(group)
        layout.addWidget(self.test_button)
        layout.addStretch(1)
        self._update_backend_visibility()

    @staticmethod
    def _section(title, rows):
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for label, widget in rows:
            form.addRow(label, widget)
        return group

    @staticmethod
    def _row_widget(widget):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return container

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

    @staticmethod
    def _available_ports():
        try:
            from serial.tools import list_ports

            return [port.device for port in list_ports.comports()]
        except Exception:
            return []

    def _refresh_port_combo(self, combo, preferred=None):
        current = preferred if isinstance(preferred, str) else combo.currentText()
        combo.clear()
        combo.addItems(self._available_ports())
        combo.setCurrentText(current or "")

    def refresh_stm32_ports(self, _checked=False):
        self._refresh_port_combo(self.stm32_port)

    def _refresh_control_modes(self, _index=None, preferred=None):
        current = preferred or self.control_mode.currentData()
        profile = MOTOR_PROFILES[self.motor_model.currentData()]
        self.control_mode.clear()
        for mode in profile.supported_control_modes:
            self.control_mode.addItem(CONTROL_MODE_LABELS[mode], mode.value)
        if not profile.supported_control_modes:
            self.control_mode.addItem("待官方參數確認", "")
        self.control_mode.setCurrentIndex(
            max(0, self.control_mode.findData(current))
        )

    @staticmethod
    def _set_row_visible(row, visible):
        form = row.parentWidget().layout()
        if hasattr(form, "setRowVisible"):
            form.setRowVisible(row, visible)
        else:
            row.setVisible(visible)

    def _update_backend_visibility(self, _index=None):
        backend = self.backend.currentData()
        self._set_row_visible(self.stm32_port_row, backend == "stm32")
        self._set_row_visible(self.stm32_baud_row, backend == "stm32")
        self._set_row_visible(self.direct_interface_row, backend == "direct_can")
        self._set_row_visible(self.direct_channel_row, backend == "direct_can")

    def settings(self):
        return {
            "backend": self.backend.currentData(),
            "motor_profile": self.motor_model.currentData(),
            "control_mode": self.control_mode.currentData(),
            "stm32_port": self.stm32_port.currentText().strip(),
            "stm32_baud": self.stm32_baud.value(),
            "can_interface": self.can_interface.currentText().strip(),
            "can_channel": self.can_channel.text().strip(),
            "can_bitrate": self.can_bitrate.value(),
            "motor_id": self.motor_id.value(),
            "command_rate_hz": self.command_rate.value(),
            "safe_torque_max": self.safe_torque.value(),
            "safe_current_a": self.safe_current.value(),
            "safe_temp_c": self.safe_temp.value(),
        }

    def set_connection_status(self, text, ok=None):
        self.connection_status.setText(text)
        color = "#15803d" if ok is True else "#b91c1c" if ok is False else "#64748b"
        self.connection_status.setStyleSheet(f"color:{color};")

    def set_running(self, running):
        self.setEnabled(not running)
