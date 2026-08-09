"""Versioned application packets exchanged between Python and STM32.

These packets are not CAN frames.  STM32 is responsible for translating a
``MotorCommand`` into the selected actuator control mode's CAN representation.
"""

from dataclasses import dataclass
from enum import IntEnum
import struct
import time
import zlib

from ..models import CanStatistics, MotorCommand, MotorTelemetry, SafetyLimits, TimestampSet
from ..motors import ControlMode

MAGIC = b"\xA5\x5A"
VERSION = 1
MAX_PAYLOAD = 4096
UINT32_NONE = 0xFFFFFFFF
UINT64_NONE = 0xFFFFFFFFFFFFFFFF

HEADER = struct.Struct("<2sBBH")
CRC = struct.Struct("<I")
COMMAND = struct.Struct("<IB3xQfffff")
TELEMETRY = struct.Struct("<I5Q4f7I")
HEARTBEAT = struct.Struct("<IQI")
CONFIGURATION = struct.Struct("<IBBBxIIfffIII")


class PacketType(IntEnum):
    MOTOR_COMMAND = 1
    MOTOR_TELEMETRY = 2
    HEARTBEAT = 3
    CONFIGURATION = 4


class PacketError(ValueError):
    pass


@dataclass(frozen=True)
class Heartbeat:
    sequence: int
    t_host_ns: int
    last_command_sequence: int | None = None


@dataclass(frozen=True)
class BackendConfiguration:
    sequence: int
    motor_id: int
    control_mode: ControlMode
    motor_profile_key: str
    can_bitrate: int
    command_rate_hz: int
    safety: SafetyLimits
    host_watchdog_ms: int = 500
    motor_command_timeout_ms: int = 250
    can_feedback_timeout_ms: int = 250


MODE_TO_WIRE = {
    ControlMode.MIT: 1,
    ControlMode.POSITION: 2,
    ControlMode.VELOCITY: 3,
    ControlMode.TORQUE: 4,
}
WIRE_TO_MODE = {value: key for key, value in MODE_TO_WIRE.items()}
PROFILE_TO_WIRE = {
    "ak10-9-v3-kv60": 1,
    "ak70-10-kv100": 2,
}
WIRE_TO_PROFILE = {value: key for key, value in PROFILE_TO_WIRE.items()}


def _u64(value: int | None) -> int:
    return UINT64_NONE if value is None else int(value)


def _u32(value: int | None) -> int:
    return UINT32_NONE if value is None else int(value)


def _optional_u64(value: int) -> int | None:
    return None if value == UINT64_NONE else value


def _optional_u32(value: int) -> int | None:
    return None if value == UINT32_NONE else value


def _payload(packet) -> tuple[PacketType, bytes]:
    if isinstance(packet, MotorCommand):
        packet.validate()
        return PacketType.MOTOR_COMMAND, COMMAND.pack(
            packet.sequence,
            MODE_TO_WIRE[packet.mode],
            _u64(packet.t_host_command_ns),
            packet.position_rad,
            packet.velocity_rads,
            packet.kp,
            packet.kd,
            packet.torque_nm,
        )
    if isinstance(packet, MotorTelemetry):
        ts = packet.timestamps
        stats = packet.can_statistics
        return PacketType.MOTOR_TELEMETRY, TELEMETRY.pack(
            packet.sequence,
            _u64(ts.t_mcu_us),
            _u64(ts.t_host_command_ns),
            _u64(ts.t_mcu_rx_us),
            _u64(ts.t_can_tx_us),
            _u64(ts.t_can_rx_us),
            packet.position_rad,
            packet.velocity_rads,
            packet.current_a,
            packet.temperature_c,
            packet.motor_error,
            _u32(stats.can_tx_count),
            _u32(stats.can_rx_count),
            _u32(stats.can_tx_error),
            _u32(stats.can_rx_error),
            _u32(stats.bus_off_count),
            _u32(stats.last_error_code),
        )
    if isinstance(packet, Heartbeat):
        return PacketType.HEARTBEAT, HEARTBEAT.pack(
            packet.sequence, packet.t_host_ns, _u32(packet.last_command_sequence)
        )
    if isinstance(packet, BackendConfiguration):
        packet.safety.validate()
        return PacketType.CONFIGURATION, CONFIGURATION.pack(
            packet.sequence,
            packet.motor_id,
            MODE_TO_WIRE[packet.control_mode],
            PROFILE_TO_WIRE[packet.motor_profile_key],
            packet.can_bitrate,
            packet.command_rate_hz,
            packet.safety.torque_nm,
            packet.safety.current_a,
            packet.safety.temperature_c,
            packet.host_watchdog_ms,
            packet.motor_command_timeout_ms,
            packet.can_feedback_timeout_ms,
        )
    raise TypeError(f"Unsupported STM32 application packet: {type(packet).__name__}")


def encode_packet(packet) -> bytes:
    packet_type, payload = _payload(packet)
    header = HEADER.pack(MAGIC, VERSION, packet_type, len(payload))
    checksum = zlib.crc32(header + payload) & 0xFFFFFFFF
    return header + payload + CRC.pack(checksum)


def decode_packet(frame: bytes):
    if len(frame) < HEADER.size + CRC.size:
        raise PacketError("STM32 packet is truncated")
    magic, version, raw_type, payload_length = HEADER.unpack_from(frame)
    if magic != MAGIC:
        raise PacketError("STM32 packet magic is invalid")
    if version != VERSION:
        raise PacketError(f"Unsupported STM32 packet version: {version}")
    if payload_length > MAX_PAYLOAD:
        raise PacketError("STM32 packet payload exceeds the configured maximum")
    expected_length = HEADER.size + payload_length + CRC.size
    if len(frame) != expected_length:
        raise PacketError("STM32 packet length does not match its header")
    expected_crc = CRC.unpack_from(frame, HEADER.size + payload_length)[0]
    actual_crc = zlib.crc32(frame[: HEADER.size + payload_length]) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise PacketError("STM32 packet CRC mismatch")
    try:
        packet_type = PacketType(raw_type)
    except ValueError as exc:
        raise PacketError(f"Unknown STM32 packet type: {raw_type}") from exc
    payload = frame[HEADER.size : HEADER.size + payload_length]
    return _decode_payload(packet_type, payload)


def _decode_payload(packet_type: PacketType, payload: bytes):
    if packet_type is PacketType.MOTOR_COMMAND:
        if len(payload) != COMMAND.size:
            raise PacketError("Motor command payload length is invalid")
        sequence, raw_mode, host_ns, position, velocity, kp, kd, torque = COMMAND.unpack(payload)
        try:
            mode = WIRE_TO_MODE[raw_mode]
        except KeyError as exc:
            raise PacketError(f"Unknown control mode value: {raw_mode}") from exc
        return MotorCommand(
            sequence=sequence,
            mode=mode,
            position_rad=position,
            velocity_rads=velocity,
            kp=kp,
            kd=kd,
            torque_nm=torque,
            t_host_command_ns=_optional_u64(host_ns),
        )
    if packet_type is PacketType.MOTOR_TELEMETRY:
        if len(payload) != TELEMETRY.size:
            raise PacketError("Motor telemetry payload length is invalid")
        values = TELEMETRY.unpack(payload)
        stats = CanStatistics(
            can_tx_count=_optional_u32(values[11]),
            can_rx_count=_optional_u32(values[12]),
            can_tx_error=_optional_u32(values[13]),
            can_rx_error=_optional_u32(values[14]),
            bus_off_count=_optional_u32(values[15]),
            last_error_code=_optional_u32(values[16]),
        )
        return MotorTelemetry(
            sequence=values[0],
            timestamps=TimestampSet(
                t_mcu_us=_optional_u64(values[1]),
                t_host_command_ns=_optional_u64(values[2]),
                t_mcu_rx_us=_optional_u64(values[3]),
                t_can_tx_us=_optional_u64(values[4]),
                t_can_rx_us=_optional_u64(values[5]),
                t_host_rx_ns=time.perf_counter_ns(),
            ),
            position_rad=values[6],
            velocity_rads=values[7],
            current_a=values[8],
            temperature_c=values[9],
            motor_error=values[10],
            can_statistics=stats,
        )
    if packet_type is PacketType.HEARTBEAT:
        if len(payload) != HEARTBEAT.size:
            raise PacketError("Heartbeat payload length is invalid")
        sequence, host_ns, last_command = HEARTBEAT.unpack(payload)
        return Heartbeat(sequence, host_ns, _optional_u32(last_command))
    if packet_type is PacketType.CONFIGURATION:
        if len(payload) != CONFIGURATION.size:
            raise PacketError("Configuration payload length is invalid")
        values = CONFIGURATION.unpack(payload)
        try:
            mode = WIRE_TO_MODE[values[2]]
        except KeyError as exc:
            raise PacketError(f"Unknown control mode value: {values[2]}") from exc
        try:
            profile_key = WIRE_TO_PROFILE[values[3]]
        except KeyError as exc:
            raise PacketError(f"Unknown motor profile value: {values[3]}") from exc
        return BackendConfiguration(
            sequence=values[0],
            motor_id=values[1],
            control_mode=mode,
            motor_profile_key=profile_key,
            can_bitrate=values[4],
            command_rate_hz=values[5],
            safety=SafetyLimits(values[6], values[7], values[8]),
            host_watchdog_ms=values[9],
            motor_command_timeout_ms=values[10],
            can_feedback_timeout_ms=values[11],
        )
    raise PacketError(f"Unhandled STM32 packet type: {packet_type}")


class PacketStreamDecoder:
    """Recover complete frames from an arbitrary byte stream."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[object]:
        self._buffer.extend(data)
        packets = []
        while True:
            start = self._buffer.find(MAGIC)
            if start < 0:
                if self._buffer[-1:] != MAGIC[:1]:
                    self._buffer.clear()
                else:
                    del self._buffer[:-1]
                break
            if start:
                del self._buffer[:start]
            if len(self._buffer) < HEADER.size:
                break
            _, _, _, payload_length = HEADER.unpack_from(self._buffer)
            if payload_length > MAX_PAYLOAD:
                del self._buffer[0]
                continue
            frame_length = HEADER.size + payload_length + CRC.size
            if len(self._buffer) < frame_length:
                break
            frame = bytes(self._buffer[:frame_length])
            try:
                packets.append(decode_packet(frame))
                del self._buffer[:frame_length]
            except PacketError:
                del self._buffer[0]
        return packets
