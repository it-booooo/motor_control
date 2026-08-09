from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .spin_boxes import StepDoubleSpinBox


class ManualControlPanel(QWidget):
    connect_requested = Signal()
    disconnect_requested = Signal()
    command_requested = Signal(dict)
    idle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.intent = QComboBox()
        self.intent.addItem("MIT Hybrid", "mit")
        self.intent.addItem("Position command through MIT", "position_mit")
        self.intent.addItem("Velocity command through MIT", "velocity_mit")
        self.intent.addItem("Torque command through MIT", "torque_mit")
        self.intent.currentIndexChanged.connect(self._update_help)

        self.position = self._number(-12.56, 12.56, 0.0, " rad")
        self.velocity = self._number(-33.0, 33.0, 0.0, " rad/s")
        self.kp = self._number(0.0, 500.0, 0.0, "")
        self.kd = self._number(0.0, 5.0, 0.0, "")
        self.torque = self._number(-65.0, 65.0, 0.0, " N·m")

        self.help = QLabel()
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color:#475569;")
        self.status = QLabel("未連線")
        self.status.setStyleSheet("color:#64748b;")
        form = QFormLayout()
        form.addRow("Command Intent", self.intent)
        form.addRow("Position", self.position)
        form.addRow("Velocity", self.velocity)
        form.addRow("Kp", self.kp)
        form.addRow("Kd", self.kd)
        form.addRow("Feedforward Torque", self.torque)

        self.connect_button = QPushButton("Connect Backend")
        self.connect_button.clicked.connect(self.connect_requested)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_requested)
        self.send_button = QPushButton("Send Logical Command")
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self._send)
        self.idle_button = QPushButton("Software Stop / Motor Idle")
        self.idle_button.setObjectName("dangerButton")
        self.idle_button.clicked.connect(self.idle_requested)
        self.warning = QLabel(
            "Position/velocity/torque presets below are implemented through MIT "
            "Control Mode. Software Stop ≠ Hardware E-Stop."
        )
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color:#b91c1c; font-weight:600;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.help)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.disconnect_button)
        layout.addWidget(self.send_button)
        layout.addWidget(self.idle_button)
        layout.addWidget(self.warning)
        layout.addStretch(1)
        self._update_help()
        self.set_connected(False)

    @staticmethod
    def _number(minimum, maximum, value, suffix):
        widget = StepDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(4)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def _update_help(self, _index=None):
        messages = {
            "mit": "MIT hybrid target: position, velocity, Kp, Kd and feedforward torque.",
            "position_mit": "Position command through MIT Control Mode; this is not native Position Mode.",
            "velocity_mit": "Velocity command through MIT Control Mode; this is not native Velocity Mode.",
            "torque_mit": "Torque feedforward through MIT Control Mode with Kp=0 and Kd=0.",
        }
        self.help.setText(messages[self.intent.currentData()])

    def _send(self):
        self.command_requested.emit(
            {
                "intent": self.intent.currentData(),
                "position_rad": self.position.value(),
                "velocity_rads": self.velocity.value(),
                "kp": self.kp.value(),
                "kd": self.kd.value(),
                "torque_nm": self.torque.value(),
            }
        )

    def set_connected(self, connected, message=None):
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.send_button.setEnabled(connected)
        self.idle_button.setEnabled(connected)
        self.status.setText(message or ("已連線" if connected else "未連線"))
        self.status.setStyleSheet(
            f"color:{'#15803d' if connected else '#64748b'};"
        )
