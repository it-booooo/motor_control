import unittest

from src.motors import decode_mit_command, encode_mit_command, get_motor_profile


class MITControlModeCodecTests(unittest.TestCase):
    def test_ak10_command_round_trip(self):
        frame = encode_mit_command(1.25, -2.5, 20.0, 1.25, 3.5)
        self.assertEqual(len(frame), 8)
        decoded = decode_mit_command(frame)
        self.assertAlmostEqual(decoded.position_rad, 1.25, delta=0.001)
        self.assertAlmostEqual(decoded.velocity_rads, -2.5, delta=0.02)
        self.assertAlmostEqual(decoded.kp, 20.0, delta=0.13)
        self.assertAlmostEqual(decoded.kd, 1.25, delta=0.002)
        self.assertAlmostEqual(decoded.torque_nm, 3.5, delta=0.04)

    def test_ak70_codec_does_not_reuse_ak10_scaling(self):
        ak70 = get_motor_profile("ak70-10-kv100")
        with self.assertRaisesRegex(ValueError, "codec is incomplete"):
            encode_mit_command(0, 0, 0, 0, 0, profile=ak70)


if __name__ == "__main__":
    unittest.main()
