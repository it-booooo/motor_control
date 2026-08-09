"""Host and MCU timestamps for the motor communication path."""

from dataclasses import dataclass


LATENCY_TIMESTAMPS_UNAVAILABLE = (
    "Required STM32 latency timestamps are not available."
)


@dataclass(frozen=True)
class TimestampSet:
    """Timing markers retained with their originating host or STM32 clock.

    Host markers use ``perf_counter_ns`` [ns]; MCU/CAN markers use the STM32
    monotonic timer [us].  The class does not synchronize those clock domains.
    """
    t_host_command_ns: int | None = None
    t_host_rx_ns: int | None = None
    t_mcu_us: int | None = None
    t_mcu_rx_us: int | None = None
    t_can_tx_us: int | None = None
    t_can_rx_us: int | None = None

    def require_mcu_latency_markers(self) -> None:
        required = (
            self.t_mcu_rx_us,
            self.t_can_tx_us,
            self.t_can_rx_us,
        )
        if any(value is None for value in required):
            raise RuntimeError(LATENCY_TIMESTAMPS_UNAVAILABLE)

    def latency_breakdown_ms(self) -> "LatencyBreakdown":
        """Return only latency intervals whose endpoints share the MCU clock.

        Raises:
            RuntimeError: If firmware did not expose all required MCU markers.
        """
        self.require_mcu_latency_markers()
        return LatencyBreakdown(
            # Host and MCU clocks cannot be subtracted without synchronization.
            host_to_mcu=None,
            mcu_to_can_tx=(self.t_can_tx_us - self.t_mcu_rx_us) / 1000.0,
            can_response=(self.t_can_rx_us - self.t_can_tx_us) / 1000.0,
        )


@dataclass(frozen=True)
class LatencyBreakdown:
    host_to_mcu: float | None
    mcu_to_can_tx: float
    can_response: float
