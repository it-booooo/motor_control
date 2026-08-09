"""Transport abstraction for the Python-to-STM32 application link."""

from abc import ABC, abstractmethod
from collections import deque
import threading
import time

from .packets import PacketStreamDecoder, encode_packet


class STM32Transport(ABC):
    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_command(self, command) -> None:
        """Send one application-level object to STM32."""

        raise NotImplementedError

    @abstractmethod
    def read_packet(self, timeout: float | None = None):
        raise NotImplementedError


class SerialSTM32Transport(STM32Transport):
    """USB CDC/UART/VCP implementation; upper layers depend only on STM32Transport."""

    def __init__(self, port: str, baud: int, *, serial_factory=None):
        self.port = port
        self.baud = baud
        self._serial_factory = serial_factory
        self._serial = None
        self._decoder = PacketStreamDecoder()
        self._packets = deque()
        self._write_lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def open(self) -> None:
        if self.is_open:
            return
        if not self.port:
            raise ValueError("STM32 port is required")
        factory = self._serial_factory
        if factory is None:
            import serial

            factory = serial.Serial
        self._serial = factory(self.port, self.baud, timeout=0.05)
        if hasattr(self._serial, "reset_input_buffer"):
            self._serial.reset_input_buffer()

    def close(self) -> None:
        serial_port, self._serial = self._serial, None
        if serial_port is not None:
            serial_port.close()

    def send_command(self, command) -> None:
        if not self.is_open:
            raise RuntimeError("STM32 transport is not open")
        data = encode_packet(command)
        with self._write_lock:
            self._serial.write(data)

    def read_packet(self, timeout: float | None = None):
        if not self.is_open:
            raise RuntimeError("STM32 transport is not open")
        if self._packets:
            return self._packets.popleft()
        deadline = None if timeout is None else time.perf_counter() + timeout
        while deadline is None or time.perf_counter() < deadline:
            waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
            chunk = self._serial.read(max(1, min(waiting, 4096)))
            if chunk:
                self._packets.extend(self._decoder.feed(chunk))
                if self._packets:
                    return self._packets.popleft()
        return None
