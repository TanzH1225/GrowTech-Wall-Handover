"""Thread-safe application state independent of Tkinter widgets."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Callable

from domain.models import HydroStatus, VisionResult
from services.events import AppEvent, EventKind, UiEventQueue


@dataclass(frozen=True)
class StateSnapshot:
    """Read-only view used by GUI code and workflow decisions."""

    current_x: int | None
    current_y: int | None
    position_valid: bool
    requested_command: str | None
    requested_x: int | None
    requested_y: int | None
    position_generation: int
    home_generation: int
    hydro_status: HydroStatus | None
    last_vision_result: VisionResult | None
    automation_state: str


class ApplicationState:
    """Own mutable state behind a condition variable; never owns widgets."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._current_x: int | None = None
        self._current_y: int | None = None
        self._position_valid = False
        self._requested_command: str | None = None
        self._requested_x: int | None = None
        self._requested_y: int | None = None
        # Generations identify newer local reports; no sequence ID is on the wire.
        self._position_generation = 0
        self._home_generation = 0
        self._hydro_status: HydroStatus | None = None
        self._last_vision_result: VisionResult | None = None
        self._automation_state = "idle"
        self._automation_history: list[str] = ["idle"]

    def apply(self, event: AppEvent) -> bool:
        """Apply an event and return whether a motion report was accepted.

        The return value lets the router keep stale or mismatched ``START`` and
        ``POS`` reports visible in the raw serial log without painting them as
        current Gantry state in the GUI.
        """

        with self._condition:
            accepted = True
            if event.kind is EventKind.GANTRY_REQUEST:
                self._invalidate_position()
                self._requested_command = str(event.data.get("command", "")) or None
                requested_x = event.data.get("x")
                requested_y = event.data.get("y")
                self._requested_x = int(requested_x) if requested_x is not None else None
                self._requested_y = int(requested_y) if requested_y is not None else None
            elif event.kind is EventKind.GANTRY_START:
                self._invalidate_position()
                start_x = int(event.data["x"])
                start_y = int(event.data["y"])
                if not (1 <= start_x <= 6 and 1 <= start_y <= 4):
                    accepted = False
                elif self._requested_x is not None and self._requested_y is not None:
                    accepted = (
                        start_x == self._requested_x and start_y == self._requested_y
                    )
                elif self._requested_command in ("G", "P"):
                    self._requested_x = start_x
                    self._requested_y = start_y
                elif self._requested_command is None:
                    # Bind an unsolicited but well-formed START to its following
                    # POS. This is useful for firmware patrol output while still
                    # preventing a later coordinate from overwriting it.
                    self._requested_command = "controller START"
                    self._requested_x = start_x
                    self._requested_y = start_y
                else:
                    # Reset, home, disable and other coordinate-less requests
                    # must not be converted into a valid position by late data.
                    accepted = False
            elif event.kind is EventKind.GANTRY_POSITION:
                x = int(event.data["x"])
                y = int(event.data["y"])
                has_expected_target = (
                    self._requested_x is not None and self._requested_y is not None
                )
                matches_expected_target = (
                    has_expected_target
                    and x == self._requested_x
                    and y == self._requested_y
                )
                has_no_pending_request = self._requested_command is None
                unknown_target_may_complete = (
                    self._requested_command in ("G", "P")
                    and not has_expected_target
                )
                legacy_home_position_may_complete = (
                    self._requested_command == "0 0" and x == 1 and y == 1
                )
                if (
                    1 <= x <= 6
                    and 1 <= y <= 4
                    and (
                        matches_expected_target
                        or has_no_pending_request
                        or unknown_target_may_complete
                        or legacy_home_position_may_complete
                    )
                ):
                    self._current_x = x
                    self._current_y = y
                    self._position_valid = True
                    self._position_generation += 1
                    self._clear_request()
                else:
                    self._invalidate_position()
                    accepted = False
            elif event.kind is EventKind.GANTRY_HOME_COMPLETE:
                self._invalidate_position()
                # Disabled firmware re-homes before continuing the command that
                # re-enabled it. Preserve any such explicit grid/G/home request
                # so its later START/POS (or home completion waiter) can finish.
                if self._requested_command is None:
                    self._set_position_blocker("gantry homed")
                self._home_generation += 1
            elif event.kind is EventKind.GANTRY_DISABLED:
                self._invalidate_position()
                self._set_position_blocker("gantry disabled")
            elif event.kind is EventKind.GANTRY_TIMEOUT:
                self._invalidate_position()
                self._set_position_blocker("gantry timeout")
            elif (
                event.kind is EventKind.CONNECTION
                and event.source == "gantry"
                and not bool(event.data.get("online"))
            ):
                self._invalidate_position()
                self._set_position_blocker("gantry offline")
            elif event.kind is EventKind.HYDRO_STATUS:
                status = event.data.get("status")
                if isinstance(status, HydroStatus):
                    self._hydro_status = status
            elif event.kind is EventKind.VISION_RESULT:
                result = event.data.get("result")
                if isinstance(result, VisionResult):
                    self._last_vision_result = result
            elif event.kind is EventKind.AUTOMATION_STATE:
                state = str(event.data.get("state", "unknown"))
                self._automation_state = state
                self._automation_history.append(state)
            self._condition.notify_all()
            return accepted

    def snapshot(self) -> StateSnapshot:
        """Return a consistent read-only state snapshot."""

        with self._condition:
            return StateSnapshot(
                current_x=self._current_x,
                current_y=self._current_y,
                position_valid=self._position_valid,
                requested_command=self._requested_command,
                requested_x=self._requested_x,
                requested_y=self._requested_y,
                position_generation=self._position_generation,
                home_generation=self._home_generation,
                hydro_status=self._hydro_status,
                last_vision_result=self._last_vision_result,
                automation_state=self._automation_state,
            )

    def automation_history(self) -> tuple[str, ...]:
        """Return state transitions captured for diagnostics and desk tests."""

        with self._condition:
            return tuple(self._automation_history)

    def wait_for_position(
        self,
        x: int,
        y: int,
        after_generation: int,
        stop_requested: Callable[[], bool],
    ) -> bool:
        """Wait interruptibly for a new matching `POS` report.

        The preserved legacy workflow has no operation deadline. This method
        deliberately keeps that behavior while allowing the Pi orchestration
        stop flag to release its own wait; it still cannot interrupt Nano motion.
        """

        # A 100-ms wake interval checks cancellation; it is not a move deadline.
        with self._condition:
            while not stop_requested():
                if (
                    self._position_generation > after_generation
                    and self._position_valid
                    and self._current_x == x
                    and self._current_y == y
                ):
                    return True
                self._condition.wait(timeout=0.1)
        return False

    def wait_for_any_position(
        self,
        after_generation: int,
        stop_requested: Callable[[], bool],
    ) -> bool:
        """Wait interruptibly for any newer accepted in-range ``POS`` report."""

        with self._condition:
            while not stop_requested():
                if self._position_generation > after_generation and self._position_valid:
                    return True
                self._condition.wait(timeout=0.1)
        return False

    def wake_waiters(self) -> None:
        """Wake condition waiters after an external cancellation request."""

        with self._condition:
            self._condition.notify_all()

    def _invalidate_position(self) -> None:
        """Mark cached coordinates stale until a fresh in-range `POS` arrives."""

        self._position_valid = False

    def _clear_request(self) -> None:
        self._requested_command = None
        self._requested_x = None
        self._requested_y = None

    def _set_position_blocker(self, reason: str) -> None:
        self._requested_command = reason
        self._requested_x = None
        self._requested_y = None

    def wait_for_home(
        self,
        after_generation: int,
        stop_requested: Callable[[], bool],
        *,
        after_position_generation: int | None = None,
        expected_position: tuple[int, int] | None = None,
    ) -> bool:
        """Wait for `Homing complete.` or an explicitly expected home POS.

        Recognizing this already-emitted line corrects the documented legacy
        `0 0`/`POS` handshake bug without changing controller wire behavior.
        """

        with self._condition:
            while not stop_requested():
                if self._home_generation > after_generation:
                    return True
                if (
                    after_position_generation is not None
                    and expected_position is not None
                    and self._position_generation > after_position_generation
                    and self._position_valid
                    and (self._current_x, self._current_y) == expected_position
                ):
                    return True
                self._condition.wait(timeout=0.1)
        return False


class ApplicationEventRouter:
    """Apply events to state and fan them out to the GUI queue."""

    def __init__(self, state: ApplicationState, ui_events: UiEventQueue) -> None:
        self._state = state
        self._ui_events = ui_events
        # State mutation and its corresponding GUI event form one ordered
        # transaction across all serial/provider/worker producers.
        self._publish_lock = threading.Lock()

    def publish(self, event: AppEvent) -> None:
        """Route a controller/worker event without accessing Tkinter."""

        with self._publish_lock:
            accepted = self._state.apply(event)
            if event.kind in (EventKind.GANTRY_START, EventKind.GANTRY_POSITION):
                event = AppEvent(
                    event.kind,
                    event.source,
                    {**event.data, "accepted": accepted},
                    timestamp=event.timestamp,
                )
            self._ui_events.publish(event)
