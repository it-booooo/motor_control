import unittest

from src.experiment_specs import estimated_duration, validate_request


class ExperimentSpecsTests(unittest.TestCase):
    def setUp(self):
        self.hardware = {
            "backend": "simulation", "motor_profile": "ak10-9-v3-kv60",
            "control_mode": "mit", "safe_torque_max": 20.0,
            "safe_current_a": 30.0, "safe_temp_c": 70.0, "command_rate_hz": 200,
        }

    def test_verify_duration(self):
        self.assertEqual(estimated_duration("verify", {"spin_duration_s": 3.0}), 5.0)

    def test_verify_rejects_zero_velocity(self):
        with self.assertRaises(ValueError):
            validate_request("verify", {"velocity_rads": 0, "spin_duration_s": 2}, self.hardware)

    def test_unknown_experiments_are_not_supported(self):
        with self.assertRaises(ValueError):
            validate_request("kt", {}, self.hardware)
