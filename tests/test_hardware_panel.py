import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.app_state import HardwareSettings
from src.ui.hardware_panel import HardwarePanel


class HardwarePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stm32_is_default_and_direct_can_fields_are_conditional(self):
        panel = HardwarePanel(HardwareSettings())
        panel.show()
        self.app.processEvents()
        self.assertEqual(panel.settings()["backend"], "stm32")
        self.assertTrue(panel.stm32_port_row.isVisible())
        self.assertFalse(panel.direct_interface_row.isVisible())

        panel.backend.setCurrentIndex(panel.backend.findData("direct_can"))
        self.app.processEvents()
        self.assertFalse(panel.stm32_port_row.isVisible())
        self.assertTrue(panel.direct_interface_row.isVisible())
        panel.close()

    def test_ak70_exposes_no_unverified_control_mode(self):
        panel = HardwarePanel(HardwareSettings())
        panel.motor_model.setCurrentIndex(
            panel.motor_model.findData("ak70-10-kv100")
        )
        self.assertEqual(panel.control_mode.currentData(), "")
        panel.close()

    def test_experiment_panel_only_exposes_motor_feedback_check(self):
        from src.ui.experiment_panel import ExperimentPanel

        panel = ExperimentPanel(20.0)
        emitted = []
        panel.start_requested.connect(lambda kind, params: emitted.append((kind, params)))
        panel._emit_start()
        self.assertEqual(emitted[0][0], "verify")
        panel.close()


if __name__ == "__main__":
    unittest.main()
