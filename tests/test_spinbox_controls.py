import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.ui.spin_boxes import StepDoubleSpinBox, StepSpinBox
from src.ui.style import APP_STYLE


class SpinBoxControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLE)

    def assert_buttons_change_value(self, widget, step):
        widget.setRange(0, 1000)
        widget.setValue(100)
        widget.resize(320, 44)
        widget.show()
        self.app.processEvents()

        self.assertGreaterEqual(widget.up_button.width(), 24)
        self.assertGreaterEqual(widget.down_button.width(), 24)
        self.assertEqual(widget.up_button.geometry().right(), widget.rect().right() - 1)
        self.assertEqual(widget.down_button.geometry().right(), widget.rect().right() - 1)

        widget.lineEdit().deselect()
        QTest.mouseClick(widget.up_button, Qt.MouseButton.LeftButton)
        self.assertAlmostEqual(widget.value(), 100 + step)
        self.assertEqual(widget.lineEdit().selectedText(), "")
        QTest.mouseClick(widget.down_button, Qt.MouseButton.LeftButton)
        self.assertAlmostEqual(widget.value(), 100)
        widget.close()

    def test_integer_spinbox_buttons(self):
        self.assert_buttons_change_value(StepSpinBox(), 1)

    def test_double_spinbox_buttons(self):
        widget = StepDoubleSpinBox()
        widget.setSingleStep(0.25)
        self.assert_buttons_change_value(widget, 0.25)


if __name__ == "__main__":
    unittest.main()
