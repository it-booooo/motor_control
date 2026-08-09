import unittest

from src.experiment_specs import validate_hardware_settings


def settings(**overrides):
    values = {
        "backend": "stm32", "motor_profile": "ak10-9-v3-kv60", "control_mode": "mit",
        "stm32_port": "COM4", "can_interface": "socketcan", "can_channel": "can0",
        "safe_torque_max": 10.0, "safe_current_a": 20.0, "safe_temp_c": 70.0,
        "command_rate_hz": 200,
    }
    values.update(overrides)
    return values


class HardwareValidationTests(unittest.TestCase):
    def test_stm32_requires_transport_port(self):
        with self.assertRaisesRegex(ValueError, "STM32 Port"):
            validate_hardware_settings(settings(stm32_port=""))

    def test_direct_can_requires_python_can_settings(self):
        with self.assertRaisesRegex(ValueError, "Direct CAN"):
            validate_hardware_settings(settings(backend="direct_can", can_interface="", can_channel=""))

    def test_simulation_needs_no_transport(self):
        validate_hardware_settings(settings(backend="simulation", stm32_port="", can_interface="", can_channel=""))
