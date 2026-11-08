"""Incremental newline framing for both Nano text protocols."""

from __future__ import annotations


class BufferedLineParser:
    """Accumulate arbitrary byte chunks and emit complete decoded lines."""

    def __init__(self, max_buffer_bytes: int = 65_536) -> None:
        self._buffer = bytearray()
        self._max_buffer_bytes = max_buffer_bytes

    @property
    def pending_bytes(self) -> bytes:
        """Return the currently incomplete record for diagnostics/tests."""

        return bytes(self._buffer)

    def feed(self, data: bytes) -> list[str]:
        """Feed a serial chunk and return all complete non-blank lines."""

        if not data:
            return []
        # Reads may split a record or contain several records; retain the
        # suffix until LF arrives rather than treating a read as one message.
        self._buffer.extend(data)
        # The limit is checked before draining this chunk, including complete
        # lines. Overflow clears the buffer and the client reports a reader error.
        if len(self._buffer) > self._max_buffer_bytes:
            self._buffer.clear()
            raise ValueError("Serial line buffer exceeded its configured limit")

        lines: list[str] = []
        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                break
            raw = bytes(self._buffer[:newline_index])
            del self._buffer[: newline_index + 1]
            decoded = raw.decode("utf-8", errors="ignore").rstrip("\r").strip()
            if decoded:
                lines.append(decoded)
        return lines

    def reset(self) -> None:
        """Discard an incomplete line after a transport reset."""

        self._buffer.clear()
