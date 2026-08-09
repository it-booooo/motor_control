from collections import deque
import time
import unittest

from src.communication import BackendConfiguration, Heartbeat
from src.devices.direct_can_backend import DirectCANMotorBackend
from src.devices.motor_backend import MotorBackend
from src.devices.simulated_backend import SimulatedMotorBackend
from src.devices.stm32_backend import STM32MotorBackend
from src.models import CanStatistics, MotorCommand, MotorTelemetry, SafetyLimits, TimestampSet
from src.motors import ControlMode, get_motor_profile


class FakeDirectMotor:
    def __init__(self):
        self.opened = False
        self.command = None

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def set_command(self, *values):
        self.command = values

    def idle(self):
        self.command = (0, 0, 0, 0, 0)

    def read(self):
        return None

    def get_can_statistics(self):
        return CanStatistics(
            can_tx_count=3, rx_timeout_count=4, filtered_frame_count=5
        )


class FakeTransport:
    def __init__(self, packets=()):
        self.packets = deque(packets)
        self.sent = []
        self.opened = False

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def send_command(self, packet):
        self.sent.append(packet)

    def read_packet(self, timeout=None):
        if self.packets:
            return self.packets.popleft()
        time.sleep(min(timeout or 0, 0.005))
        return None


class MotorBackendTests(unittest.TestCase):
    def setUp(self):
        self.profile = get_motor_profile("ak10-9-v3-kv60")

    def test_simulation_implements_backend_interface(self):
        backend = SimulatedMotorBackend(self.profile)
        self.assertIsInstance(backend, MotorBackend)
        backend.open()
        backend.torque(2.0)
        state = backend.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(backend.last_command.mode, ControlMode.MIT)
        backend.idle()
        self.assertEqual(backend.last_command.torque_nm, 0.0)
        backend.close()

    def test_legacy_direct_can_adapter_remains_compatible(self):
        motor = FakeDirectMotor()
        backend = DirectCANMotorBackend(
            self.profile,
            motor_id=1,
            interface="virtual",
            channel="test",
            bitrate=1_000_000,
            command_rate_hz=200,
            motor=motor,
        )
        backend.open()
        backend.torque(1.5)
        self.assertEqual(motor.command, (0.0, 0.0, 0.0, 0.0, 1.5))
        self.assertEqual(backend.get_can_statistics().can_tx_count, 3)
        self.assertEqual(backend.get_can_statistics().rx_timeout_count, 4)
        self.assertEqual(backend.get_can_statistics().filtered_frame_count, 5)
        backend.close()

    def test_stm32_backend_sends_application_objects(self):
        telemetry = MotorTelemetry(
            sequence=1,
            timestamps=TimestampSet(t_host_rx_ns=time.perf_counter_ns()),
            position_rad=0.0,
            velocity_rads=0.0,
            current_a=0.0,
            temperature_c=25.0,
            motor_error=0,
        )
        transport = FakeTransport([telemetry])
        backend = STM32MotorBackend(
            self.profile,
            motor_id=1,
            port="ignored",
            baud=115200,
            can_bitrate=1_000_000,
            command_rate_hz=200,
            safety=SafetyLimits(10.0, 20.0, 70.0),
            transport=transport,
            heartbeat_hz=100.0,
        )
        backend.open()
        deadline = time.time() + 0.2
        while backend.read_state() is None and time.time() < deadline:
            time.sleep(0.005)
        backend.torque(1.0)
        backend.close()
        self.assertTrue(any(isinstance(item, BackendConfiguration) for item in transport.sent))
        self.assertTrue(any(isinstance(item, Heartbeat) for item in transport.sent))
        self.assertTrue(any(isinstance(item, MotorCommand) for item in transport.sent))


if __name__ == "__main__":
    unittest.main()
