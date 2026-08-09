import unittest

from src.communication import BackendConfiguration, PacketError, PacketStreamDecoder, decode_packet, encode_packet
from src.models import CanStatistics, MotorCommand, MotorTelemetry, SafetyLimits, TimestampSet
from src.motors import ControlMode


class STM32PacketTests(unittest.TestCase):
    def test_motor_command_round_trip(self):
        command = MotorCommand(42, ControlMode.MIT, 1.0, 2.0, 3.0, 4.0, 5.0, 123456)
        decoded = decode_packet(encode_packet(command))
        self.assertEqual(decoded.sequence, 42)
        self.assertEqual(decoded.mode, ControlMode.MIT)
        self.assertEqual(decoded.t_host_command_ns, 123456)
        self.assertAlmostEqual(decoded.torque_nm, 5.0)

    def test_motor_telemetry_round_trip(self):
        telemetry = MotorTelemetry(
            sequence=7,
            timestamps=TimestampSet(t_mcu_us=1000, t_host_command_ns=2000,
                                    t_mcu_rx_us=101, t_can_tx_us=111, t_can_rx_us=121),
            position_rad=0.5, velocity_rads=1.5, current_a=2.5,
            temperature_c=35.0, motor_error=0,
            can_statistics=CanStatistics(can_tx_count=10, bus_off_count=None),
        )
        decoded = decode_packet(encode_packet(telemetry))
        self.assertEqual(decoded.timestamps.t_mcu_us, 1000)
        self.assertIsNotNone(decoded.timestamps.t_host_rx_ns)
        self.assertAlmostEqual(decoded.position_rad, 0.5)
        self.assertEqual(decoded.can_statistics.can_tx_count, 10)
        self.assertIsNone(decoded.can_statistics.bus_off_count)

    def test_configuration_identifies_motor_profile(self):
        config = BackendConfiguration(1, 2, ControlMode.MIT, "ak10-9-v3-kv60",
                                     1_000_000, 200, SafetyLimits(10.0, 20.0, 70.0))
        decoded = decode_packet(encode_packet(config))
        self.assertEqual(decoded.motor_profile_key, "ak10-9-v3-kv60")

    def test_crc_rejects_corruption(self):
        frame = bytearray(encode_packet(MotorCommand.idle(ControlMode.MIT)))
        frame[-1] ^= 1
        with self.assertRaisesRegex(PacketError, "CRC"):
            decode_packet(bytes(frame))

    def test_stream_decoder_handles_split_frame(self):
        frame = encode_packet(MotorCommand.idle(ControlMode.MIT))
        decoder = PacketStreamDecoder()
        self.assertEqual(decoder.feed(b"noise" + frame[:5]), [])
        packets = decoder.feed(frame[5:])
        self.assertEqual(len(packets), 1)


if __name__ == "__main__":
    unittest.main()
