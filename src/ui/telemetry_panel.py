from collections import deque
import time

from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
except ImportError:  # The text telemetry remains usable without the optional plot package.
    pg = None


class TelemetryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value_labels = {}
        fields = [
            ("phase", "階段", "—"),
            ("position", "位置", "— °"),
            ("speed", "速度", "— rad/s"),
            ("current", "電流", "— A"),
            ("temperature", "溫度", "— °C"),
            ("force", "Load cell", "— N"),
            ("torque", "實測扭力", "— N·m"),
            ("cmd_torque", "指令扭力", "— N·m"),
        ]
        cards = QGridLayout()
        for index, (key, title, initial) in enumerate(fields):
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            label = QLabel(initial)
            label.setStyleSheet("font-size:15pt; font-weight:600; color:#0f172a;")
            box_layout.addWidget(label)
            self.value_labels[key] = label
            cards.addWidget(box, index // 4, index % 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(cards)
        self._start = time.monotonic()
        self.times = deque(maxlen=1200)
        self.torque_values = deque(maxlen=1200)
        self.current_values = deque(maxlen=1200)
        self.temp_values = deque(maxlen=1200)
        if pg is not None:
            pg.setConfigOptions(antialias=True, background="#ffffff", foreground="#475569")
            self.plot = pg.PlotWidget()
            self.plot.setLabel("bottom", "Time", units="s")
            self.plot.showGrid(x=True, y=True, alpha=0.18)
            self.plot.addLegend(offset=(10, 10))
            self.torque_curve = self.plot.plot(pen=pg.mkPen("#2563eb", width=2), name="Torque (N·m)")
            self.current_curve = self.plot.plot(pen=pg.mkPen("#f59e0b", width=1.5), name="Current (A)")
            self.temp_curve = self.plot.plot(pen=pg.mkPen("#dc2626", width=1.5), name="Temp (°C)")
            layout.addWidget(self.plot, 1)
        else:
            notice = QLabel("未安裝 pyqtgraph：即時數值可用，曲線圖停用。")
            notice.setStyleSheet("color:#b45309;")
            layout.addWidget(notice)

    def reset(self):
        self._start = time.monotonic()
        self.times.clear()
        self.torque_values.clear()
        self.current_values.clear()
        self.temp_values.clear()
        if pg is not None:
            self.torque_curve.clear()
            self.current_curve.clear()
            self.temp_curve.clear()

    def update_telemetry(self, values):
        formats = {
            "position": "{:+.2f} °",
            "speed": "{:+.3f} rad/s",
            "current": "{:+.2f} A",
            "temperature": "{:.1f} °C",
            "force": "{:+.3f} N",
            "torque": "{:+.3f} N·m",
            "cmd_torque": "{:+.2f} N·m",
        }
        for key, value in values.items():
            if key not in self.value_labels:
                continue
            self.value_labels[key].setText(
                str(value) if key == "phase" else formats[key].format(value)
            )
        now = time.monotonic() - self._start
        self.times.append(now)
        self.torque_values.append(values.get("torque", self.torque_values[-1] if self.torque_values else 0.0))
        self.current_values.append(values.get("current", self.current_values[-1] if self.current_values else 0.0))
        self.temp_values.append(values.get("temperature", self.temp_values[-1] if self.temp_values else 0.0))
        if pg is not None:
            x = list(self.times)
            self.torque_curve.setData(x, list(self.torque_values))
            self.current_curve.setData(x, list(self.current_values))
            self.temp_curve.setData(x, list(self.temp_values))
