"""Hardware-mode controller clients; none open hardware during import."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from comm.line_parser import BufferedLineParser
from comm.protocols import (
    arm_group_run_frame,
    arm_group_stop_frame,
    line_command,
    parse_gantry_report,
    parse_hydro_status,
)
from comm.serial_transport import SerialTransport
from config.settings import SerialEndpointConfig
from services.events import AppEvent, EventKind


EventSink = Callable[[AppEvent], None]


class _TextSerialClient:
    """Shared lifecycle and buffered reader for newline-framed controllers."""

    def __init__(self, name: str, config: SerialEndpointConfig, sink: EventSink) -> None:
        self._name = name
        self._transport = SerialTransport(config)
        self._sink = sink
        self._lines = BufferedLineParser()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger(f"comm.{name}")

    def start(self) -> None:
        # Each Nano client owns its own reader and partial-line buffer; the
        # sink publishes events and must not update Tk widgets from this thread.
        self._transport.open()
        self._stop.clear()
        try:
            self._thread = threading.Thread(
                target=self._read_loop,
                name=f"{self._name}-serial-reader",
                daemon=True,
            )
            self._thread.start()
            self._sink(
                AppEvent(EventKind.CONNECTION, self._name, {"online": True})
            )
        except Exception:
            self._stop.set()
            self._transport.close()
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            self._thread = None
            raise

    def stop(self) -> None:
        self._stop.set()
        self._transport.close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._lines.reset()
        self._sink(
            AppEvent(EventKind.CONNECTION, self._name, {"online": False})
        )

    def send(self, command: str) -> None:
        try:
            self._transport.write(line_command(command))
        except Exception:
            self._sink(
                AppEvent(EventKind.CONNECTION, self._name, {"online": False})
            )
            raise
        # Sent means the transport write returned, not that the Nano accepted
        # or completed this command; legacy reports have no transaction ID.
        self._sink(AppEvent(EventKind.LOG, self._name, {"message": f"Sent: {command}"}))

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._transport.read_available()
                for line in self._lines.feed(chunk):
                    self._handle_line(line)
            except Exception as exc:
                self._logger.exception("Serial reader failed")
                self._sink(
                    AppEvent(EventKind.ERROR, self._name, {"message": str(exc)})
                )
                self._sink(
                    AppEvent(EventKind.CONNECTION, self._name, {"online": False})
                )
                break
            self._stop.wait(0.01)

    def _handle_line(self, line: str) -> None:
        raise NotImplementedError


class GantrySerialClient(_TextSerialClient):
    """Gantry Nano text client with source-compatible response parsing."""

    def __init__(self, config: SerialEndpointConfig, sink: EventSink) -> None:
        super().__init__("gantry", config, sink)

    def _handle_line(self, line: str) -> None:
        self._sink(AppEvent(EventKind.GANTRY_RAW, "gantry", {"line": line}))
        report = parse_gantry_report(line)
        if report.kind == "start":
            self._sink(
                AppEvent(
                    EventKind.GANTRY_START,
                    "gantry",
                    {"x": report.x, "y": report.y},
                )
            )
        elif report.kind == "pos":
            self._sink(
                AppEvent(
                    EventKind.GANTRY_POSITION,
                    "gantry",
                    {"x": report.x, "y": report.y},
                )
            )
        elif report.kind == "home_complete":
            self._sink(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
        elif report.kind == "disabled":
            self._sink(AppEvent(EventKind.GANTRY_DISABLED, "gantry"))
        elif report.kind == "timeout":
            self._sink(
                AppEvent(EventKind.GANTRY_TIMEOUT, "gantry", {"detail": report.detail})
            )
        elif report.kind == "malformed":
            self._sink(
                AppEvent(
                    EventKind.ERROR,
                    "gantry",
                    {"message": f"Malformed gantry report: {line}"},
                )
            )


class HydroponicsSerialClient(_TextSerialClient):
    """Hydroponics Nano client with fixed complete-line buffering."""

    def __init__(self, config: SerialEndpointConfig, sink: EventSink) -> None:
        super().__init__("hydroponics", config, sink)

    def _handle_line(self, line: str) -> None:
        self._sink(AppEvent(EventKind.HYDRO_RAW, "hydroponics", {"line": line}))
        if not line.startswith("STAT,"):
            return
        status = parse_hydro_status(line)
        if status is None:
            self._sink(
                AppEvent(
                    EventKind.ERROR,
                    "hydroponics",
                    {"message": f"Malformed hydroponics status: {line}"},
                )
            )
            return
        self._sink(
            AppEvent(EventKind.HYDRO_STATUS, "hydroponics", {"status": status})
        )


class ArmSerialClient:
    """Write-only Lobot action-group client for native `/dev/ttyAMA1`."""

    def __init__(self, config: SerialEndpointConfig, sink: EventSink) -> None:
        self._transport = SerialTransport(config)
        self._sink = sink

    def start(self) -> None:
        self._transport.open()
        self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": True}))

    def stop(self) -> None:
        self._transport.close()
        self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": False}))

    def run_group(self, group_id: int, repeat_count: int = 1) -> None:
        try:
            self._transport.write(arm_group_run_frame(group_id, repeat_count))
        except Exception:
            self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": False}))
            raise
        # This state is inferred from the write. There is no arm receive loop
        # or completion report; WorkflowService applies the configured fixed wait.
        self._sink(
            AppEvent(EventKind.ARM_STATE, "arm", {"state": f"Running Group {group_id}"})
        )

    def stop_group(self) -> None:
        try:
            self._transport.write(arm_group_stop_frame())
        except Exception:
            self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": False}))
            raise
        self._sink(AppEvent(EventKind.ARM_STATE, "arm", {"state": "Stopped"}))
