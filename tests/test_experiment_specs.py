import unittest

from src.experiment_specs import estimated_duration, validate_request


class ExperimentSpecsTests(unittest.TestCase):
    def setUp(self):
        self.hardware = {
            "safe_torque_max": 20.0,
            "lever_m": 0.15,
            "can_interface": "socketcan",
            "can_channel": "can0",
            "loadcell_port": "COM3",
        }

    def test_duration_estimates_cover_all_measurement_phases(self):
        self.assertEqual(
            estimated_duration(
                "kt", {"steps": 10, "hold_s": 3.0, "rest_s": 5.0}
            ),
            82.0,
        )
        self.assertEqual(
            estimated_duration(
                "thermal",
                {"duration_s": 600.0, "cooldown_s": 300.0},
            ),
            910.0,
        )

    def test_rejects_torque_above_safety_limit(self):
        with self.assertRaisesRegex(ValueError, "超過軟體安全上限"):
            validate_request(
                "kt",
                {"torque_max": 21.0, "steps": 10, "hold_s": 3.0, "rest_s": 5.0},
                self.hardware,
            )

    def test_allows_negative_thermal_torque_with_absolute_limit(self):
        validate_request(
            "thermal",
            {"torque": -10.0, "duration_s": 20.0, "cooldown_s": 5.0},
            self.hardware,
        )

    def test_rejects_invalid_lever_length(self):
        hardware = dict(self.hardware, lever_m=0.0)
        with self.assertRaisesRegex(ValueError, "力臂長度"):
            validate_request(
                "backdrive", {"duration_s": 10.0}, hardware
            )

    def test_verify_does_not_require_loadcell(self):
        hardware = dict(self.hardware, loadcell_port="")
        validate_request(
            "verify",
            {"velocity_rads": 2.0, "spin_duration_s": 3.0},
            hardware,
        )


if __name__ == "__main__":
    unittest.main()
