"""Thread-safe events passed from transports/workers to the Tk main thread."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
import time
from typing import Mapping


class EventKind(str, Enum):
    """Stable event names understood by application state and the GUI."""

    LOG = "log"
    ERROR = "error"
    CONNECTION = "connection"
    GANTRY_RAW = "gantry.raw"
    GANTRY_REQUEST = "gantry.request"
    GANTRY_START = "gantry.start"
    GANTRY_POSITION = "gantry.position"
    GANTRY_HOME_COMPLETE = "gantry.home_complete"
    GANTRY_DISABLED = "gantry.disabled"
    GANTRY_TIMEOUT = "gantry.timeout"
    HYDRO_RAW = "hydro.raw"
    HYDRO_STATUS = "hydro.status"
    ARM_STATE = "arm.state"
    VISION_RESULT = "vision.result"
    AUTOMATION_STATE = "automation.state"
    OPERATION_STATE = "operation.state"
    OPERATOR_NOTICE = "operator.notice"


@dataclass(frozen=True)
class AppEvent:
    """One immutable envelope; payload objects are treated as read-only."""

    kind: EventKind
    source: str
    data: Mapping[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class UiEventQueue:
    """Multi-producer queue drained only by the Tk main thread."""

    def __init__(self) -> None:
        self._queue: Queue[AppEvent] = Queue()

    def publish(self, event: AppEvent) -> None:
        """Enqueue an event from any controller or worker thread."""

        self._queue.put(event)

    def drain(self, limit: int = 200) -> list[AppEvent]:
        """Remove up to *limit* events without blocking the caller."""

        events: list[AppEvent] = []
        for _ in range(limit):
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        return events

    @property
    def pending(self) -> int:
        """Approximate queue depth for diagnostics."""

        return self._queue.qsize()
