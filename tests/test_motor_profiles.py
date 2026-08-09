import unittest

from src.motors import CommunicationType, ControlMode, get_motor_profile


class MotorProfileTests(unittest.TestCase):
    def test_communication_and_control_mode_are_distinct(self):
        self.assertEqual(CommunicationType.CAN.value, "can")
        self.assertEqual(ControlMode.MIT.value, "mit")
        self.assertNotIsInstance(ControlMode.MIT, CommunicationType)

    def test_lookup_returns_isolated_profiles(self):
        ak10 = get_motor_profile("ak10-9-v3-kv60")
        ak70 = get_motor_profile("ak70-10-kv100")
        self.assertEqual(ak10.communication, CommunicationType.CAN)
        self.assertIn(ControlMode.MIT, ak10.supported_control_modes)
        self.assertIsNone(ak70.p_min)
        self.assertIsNone(ak70.gear_ratio)
        self.assertNotEqual(ak10.key, ak70.key)

    def test_incomplete_ak70_profile_blocks_hardware(self):
        ak70 = get_motor_profile("ak70-10-kv100")
        with self.assertRaisesRegex(ValueError, "尚未確認支援"):
            ak70.require_hardware_parameters(ControlMode.MIT)


if __name__ == "__main__":
    unittest.main()
