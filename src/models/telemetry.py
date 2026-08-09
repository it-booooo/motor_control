"""Telemetry shared by STM32, direct-CAN and simulated backends."""

from dataclasses import dataclass, field
import math

from .timestamps import TimestampSet


@dataclass
class CanStatistics:
    can_tx_count: int | None = None
    can_rx_count: int | None = None
    can_tx_error: int | None = None
    can_rx_error: int | None = None
    rx_timeout_count: int | None = None
    filtered_frame_count: int | None = None
    bus_off_count: int | None = None
    last_error: str | None = None
    last_error_code: int | None = None


@dataclass(frozen=True)
class MotorTelemetry:
    sequence: int
    timestamps: TimestampSet
    position_rad: float
    velocity_rads: float
    current_a: float
    temperature_c: float
    motor_error: int
    can_statistics: CanStatistics = field(default_factory=CanStatistics)


@dataclass(frozen=True)
class MotorStateSnapshot:
    """Compatibility view consumed by the existing recorder/experiment code."""

    t: float
    pos_deg: float
    pos_rad: float
    spd_erpm: float | None
    spd_rads: float
    current_a: float
    temp_c: float
    error: int
    telemetry: MotorTelemetry | None = None
    age_can_s: float | None = None

    @classmethod
    def from_telemetry(cls, telemetry: MotorTelemetry) -> "MotorStateSnapshot":
        host_ns = telemetry.timestamps.t_host_rx_ns
        t = host_ns / 1_000_000_000 if host_ns is not None else 0.0
        age_can = None
        if (
            telemetry.timestamps.t_mcu_us is not None
            and telemetry.timestamps.t_can_rx_us is not None
        ):
            age_can = max(
                0.0,
                (telemetry.timestamps.t_mcu_us - telemetry.timestamps.t_can_rx_us)
                / 1_000_000.0,
            )
        return cls(
            t=t,
            pos_deg=math.degrees(telemetry.position_rad),
            pos_rad=telemetry.position_rad,
            spd_erpm=None,
            spd_rads=telemetry.velocity_rads,
            current_a=telemetry.current_a,
            temp_c=telemetry.temperature_c,
            error=telemetry.motor_error,
            telemetry=telemetry,
            age_can_s=age_can,
        )
