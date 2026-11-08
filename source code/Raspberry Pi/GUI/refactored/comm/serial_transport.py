"""Lazy pyserial adapter; importing this module never opens a device."""

from __future__ import annotations

import threading
import time
from typing import Any

from config.settings import SerialEndpointConfig
from utils.errors import HardwareUnavailableError


class SerialTransport:
    """One explicitly opened serial endpoint with serialized writes."""

    def __init__(self, config: SerialEndpointConfig) -> None:
        self._config = config
        self._serial: Any | None = None
        self._write_lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        handle = self._serial
        return bool(handle is not None and getattr(handle, "is_open", True))

    def open(self) -> None:
        """Import pyserial and open the configured endpoint explicitly."""

        if self.is_open:
            return
        handle: Any | None = None
        try:
            import serial  # type: ignore[import-not-found]

            handle = serial.Serial(
                self._config.port,
                self._config.baud_rate,
                timeout=self._config.timeout_seconds,
            )
            self._serial = handle
            if self._config.startup_settle_seconds:
                time.sleep(self._config.startup_settle_seconds)
            # The legacy GUI resets both Nano buffers after its two-second
            # settle, while ServoControl opens native UART without a reset.
            if self._config.reset_buffers_on_open:
                reset_input = getattr(self._serial, "reset_input_buffer", None)
                reset_output = getattr(self._serial, "reset_output_buffer", None)
                if reset_input:
                    reset_input()
                if reset_output:
                    reset_output()
        except Exception as exc:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            self._serial = None
            raise HardwareUnavailableError(
                f"Could not open {self._config.port} at "
                f"{self._config.baud_rate} baud: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the endpoint if it was opened."""

        handle, self._serial = self._serial, None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass

    def write(self, payload: bytes) -> None:
        """Write one complete protocol payload."""

        handle = self._serial
        if handle is None:
            raise HardwareUnavailableError(f"Serial endpoint {self._config.port} is closed")
        # The lock keeps payload bytes together across callers. It does not
        # reserve a controller until motion ends or correlate later status lines.
        with self._write_lock:
            handle.write(payload)

    def read_available(self) -> bytes:
        """Read only currently buffered bytes, avoiding an unbounded read wait.

        The Hydroponics endpoint retains its legacy `timeout=None` setting. The
        previous reader called a blocking one-byte read when no data was ready;
        skipping that read is the documented fragmented-input/shutdown bug fix.
        """

        handle = self._serial
        if handle is None:
            return b""
        # Idle polling remains cancellable even for Hydroponics timeout=None;
        # serial read timeout and a workflow completion deadline are separate.
        waiting = int(getattr(handle, "in_waiting", 0))
        return handle.read(waiting) if waiting > 0 else b""
