from collections import deque
import time

from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
except ImportError:
    pg = None


class TelemetryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value_labels = {}
        fields = [
            ("phase", "狀態", "—"), ("backend", "Backend", "—"),
            ("position", "馬達位置", "— rad"), ("speed", "馬達速度", "— rad/s"),
            ("current", "馬達電流", "— A"), ("temperature", "馬達溫度", "— °C"),
            ("cmd_torque", "命令扭矩", "— N·m"), ("can_tx", "CAN TX", "—"),
            ("can_rx", "CAN RX", "—"), ("can_errors", "CAN Errors", "—"),
            ("latency_mcu_can", "MCU → CAN TX", "— ms"),
            ("latency_can_response", "CAN Response", "— ms"),
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
        layout.addLayout(cards)
        self._start = time.monotonic()
        self.times = deque(maxlen=1200)
        self.current_values = deque(maxlen=1200)
        self.temp_values = deque(maxlen=1200)
        if pg is not None:
            pg.setConfigOptions(antialias=True, background="#ffffff", foreground="#475569")
            self.plot = pg.PlotWidget()
            self.plot.setLabel("bottom", "Time", units="s")
            self.plot.showGrid(x=True, y=True, alpha=0.18)
            self.plot.addLegend(offset=(10, 10))
            self.current_curve = self.plot.plot(pen=pg.mkPen("#2563eb", width=2), name="Current (A)")
            self.temp_curve = self.plot.plot(pen=pg.mkPen("#dc2626", width=2), name="Temperature (°C)")
            layout.addWidget(self.plot, 1)

    def reset(self):
        self._start = time.monotonic()
        self.times.clear(); self.current_values.clear(); self.temp_values.clear()
        if pg is not None:
            self.current_curve.clear(); self.temp_curve.clear()

    def update_telemetry(self, values):
        formats = {
            "position": "{:+.4f} rad", "speed": "{:+.3f} rad/s",
            "current": "{:+.2f} A", "temperature": "{:.1f} °C",
            "cmd_torque": "{:+.2f} N·m", "can_tx": "{:.0f}",
            "can_rx": "{:.0f}", "can_errors": "{:.0f}",
            "latency_mcu_can": "{:.3f} ms", "latency_can_response": "{:.3f} ms",
        }
        for key, value in values.items():
            if key not in self.value_labels or value is None:
                continue
            self.value_labels[key].setText(str(value) if key in {"phase", "backend"} else formats[key].format(value))
        self.times.append(time.monotonic() - self._start)
        self.current_values.append(values.get("current", self.current_values[-1] if self.current_values else 0.0))
        self.temp_values.append(values.get("temperature", self.temp_values[-1] if self.temp_values else 0.0))
        if pg is not None:
            x = list(self.times)
            self.current_curve.setData(x, list(self.current_values))
            self.temp_curve.setData(x, list(self.temp_values))
