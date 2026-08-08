from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AnalysisPanel(QWidget):
    analyze_requested = Signal(str)
    simulate_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("選擇實驗 CSV…")
        choose = QPushButton("選擇 CSV…")
        choose.clicked.connect(self.choose_file)
        self.analyze_button = QPushButton("執行分析")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.clicked.connect(self._analyze)
        self.simulate_button = QPushButton("產生四組模擬資料")
        self.simulate_button.clicked.connect(self.simulate_requested)
        self.stop_button = QPushButton("停止處理")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested)

        controls = QHBoxLayout()
        controls.addWidget(self.file_path, 1)
        controls.addWidget(choose)
        controls.addWidget(self.analyze_button)
        controls.addWidget(self.simulate_button)
        controls.addWidget(self.stop_button)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setMinimumHeight(125)

        self.preview_widget = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview = QScrollArea()
        self.preview.setWidgetResizable(True)
        self.preview.setWidget(self.preview_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(controls)
        layout.addWidget(self.log)
        layout.addWidget(self.preview, 1)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇實驗 CSV", self.file_path.text() or str(Path.cwd() / "data"), "CSV (*.csv)"
        )
        if path:
            self.set_file(path)
        return path

    def set_file(self, path):
        self.file_path.setText(str(path))

    def _analyze(self):
        self.analyze_requested.emit(self.file_path.text().strip())

    def append_log(self, text):
        self.log.appendPlainText(text)

    def clear_log(self):
        self.log.clear()

    def set_busy(self, busy):
        self.analyze_button.setEnabled(not busy)
        self.simulate_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

    def set_images(self, paths):
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not paths:
            label = QLabel("分析完成後，圖表會顯示在這裡。")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_layout.addWidget(label)
            return
        for path in paths:
            title = QLabel(Path(path).name)
            title.setStyleSheet("font-weight:600; margin-top:8px;")
            image = QLabel()
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                image.setPixmap(pixmap.scaledToWidth(900, Qt.TransformationMode.SmoothTransformation))
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_layout.addWidget(title)
            self.preview_layout.addWidget(image)
