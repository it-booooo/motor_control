import unittest

from src.models import LATENCY_TIMESTAMPS_UNAVAILABLE, SafetyLimits, TimestampSet


class TimestampAndSafetyTests(unittest.TestCase):
    def test_latency_breakdown_uses_only_mcu_clock_differences(self):
        result = TimestampSet(t_mcu_rx_us=1000, t_can_tx_us=1300,
                              t_can_rx_us=1600).latency_breakdown_ms()
        self.assertIsNone(result.host_to_mcu)
        self.assertAlmostEqual(result.mcu_to_can_tx, 0.3)
        self.assertAlmostEqual(result.can_response, 0.3)

    def test_missing_latency_marker_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, LATENCY_TIMESTAMPS_UNAVAILABLE):
            TimestampSet(t_mcu_rx_us=1, t_can_tx_us=2).latency_breakdown_ms()

    def test_safety_limits_must_be_positive(self):
        SafetyLimits(1.0, 2.0, 3.0).validate()
        with self.assertRaisesRegex(ValueError, "positive"):
            SafetyLimits(0.0, 2.0, 3.0).validate()
