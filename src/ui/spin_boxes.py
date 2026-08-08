from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QSpinBox,
    QToolButton,
)


class _StepButtonMixin:
    BUTTON_WIDTH = 26

    def _install_step_buttons(self):
        # Windows' native arrows can be painted outside the hit rectangles after
        # QSS changes the spin-box padding. Use real child buttons so what the
        # user sees and what Qt receives are always the same rectangle.
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.up_button = self._step_button(
            "spinStepUp", Qt.ArrowType.UpArrow, "增加數值", self.stepUp
        )
        self.down_button = self._step_button(
            "spinStepDown", Qt.ArrowType.DownArrow, "減少數值", self.stepDown
        )
        self.lineEdit().setTextMargins(0, 0, self.BUTTON_WIDTH + 4, 0)
        self._layout_step_buttons()

    def _step_button(self, name, arrow, description, callback):
        button = QToolButton(self)
        button.setObjectName(name)
        button.setArrowType(arrow)
        button.setToolTip(description)
        button.setAccessibleName(description)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(400)
        button.setAutoRepeatInterval(80)
        button.clicked.connect(
            lambda _checked=False: self._apply_step(callback)
        )
        return button

    def _apply_step(self, callback):
        callback()
        # QAbstractSpinBox selects the complete formatted value after stepBy().
        # A step-button click should not look like a click in the text editor.
        self.lineEdit().deselect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_step_buttons()

    def _layout_step_buttons(self):
        content_height = max(2, self.height() - 2)
        upper_height = content_height // 2
        x = max(0, self.width() - self.BUTTON_WIDTH - 1)
        self.up_button.setGeometry(x, 1, self.BUTTON_WIDTH, upper_height)
        self.down_button.setGeometry(
            x,
            1 + upper_height,
            self.BUTTON_WIDTH,
            content_height - upper_height,
        )
        self.up_button.raise_()
        self.down_button.raise_()


class StepSpinBox(_StepButtonMixin, QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._install_step_buttons()


class StepDoubleSpinBox(_StepButtonMixin, QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._install_step_buttons()
