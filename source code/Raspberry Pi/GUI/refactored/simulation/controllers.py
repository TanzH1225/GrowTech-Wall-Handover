"""Deterministic in-memory controller doubles that never import pyserial."""

from __future__ import annotations

import threading
from typing import Callable

from comm.protocols import parse_hydro_status
from domain.models import HydroStatus
from services.events import AppEvent, EventKind


EventSink = Callable[[AppEvent], None]
TimeoutCancel = Callable[[], None]
TimeoutScheduler = Callable[[float, Callable[[], None]], TimeoutCancel]


def _schedule_timeout(seconds: float, callback: Callable[[], None]) -> TimeoutCancel:
    """Schedule a daemon timeout used only by the laptop simulation."""

    timer = threading.Timer(seconds, callback)
    timer.daemon = True
    timer.start()
    return timer.cancel


class _CommandRecorder:
    def __init__(self) -> None:
        self._commands: list[str] = []
        self._lock = threading.Lock()
        self._started = False

    @property
    def commands(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._commands)

    def _record(self, command: str) -> None:
        with self._lock:
            if not self._started:
                raise RuntimeError("Simulated controller has not been started")
            self._commands.append(command)


class MockGantryController(_CommandRecorder):
    """Immediate Gantry Nano simulation preserving command/report text."""

    def __init__(self, sink: EventSink) -> None:
        super().__init__()
        self._sink = sink
        self._x = 0
        self._y = 0
        self._disabled = False

    def start(self) -> None:
        # Opening a Nano USB port resets the firmware to its startup state.
        self._x = 0
        self._y = 0
        self._started = True
        self._disabled = False
        self._sink(AppEvent(EventKind.CONNECTION, "gantry", {"online": True}))
        self._sink(AppEvent(EventKind.GANTRY_RAW, "gantry", {"line": "Homing complete."}))
        self._sink(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))

    def stop(self) -> None:
        self._started = False
        self._sink(AppEvent(EventKind.CONNECTION, "gantry", {"online": False}))

    def send(self, command: str) -> None:
        self._record(command)
        if command == "O":
            self._disabled = True
            self._sink(AppEvent(EventKind.GANTRY_RAW, "gantry", {"line": "Motors disabled."}))
            self._sink(AppEvent(EventKind.GANTRY_DISABLED, "gantry"))
            return
        if self._disabled:
            self._disabled = False
            self._x, self._y = 0, 0
            self._sink(
                AppEvent(
                    EventKind.GANTRY_RAW,
                    "gantry",
                    {"line": "Re-enabling motors and re-homing."},
                )
            )
            self._sink(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
        if command == "0 0":
            # The firmware does not emit POS for home. The separate completion
            # event models its existing `Homing complete.` descriptive line.
            self._x, self._y = 0, 0
            self._sink(AppEvent(EventKind.GANTRY_RAW, "gantry", {"line": "Homing complete."}))
            self._sink(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
            return
        parts = command.split()
        if len(parts) == 2:
            try:
                x, y = int(parts[0]), int(parts[1])
            except ValueError:
                x, y = 0, 0
            if 1 <= x <= 6 and 1 <= y <= 4:
                self._sink(AppEvent(EventKind.GANTRY_START, "gantry", {"x": x, "y": y}))
                self._x, self._y = x, y
                self._sink(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": x, "y": y}))
                return
        if command == "G":
            if self._x == 0 and self._y == 0:
                self._x, self._y = 1, 1
            elif self._y % 2 == 1:
                if self._x < 6:
                    self._x += 1
                elif self._y < 4:
                    self._y += 1
                    self._x = 6
                else:
                    self._x, self._y = 1, 1
            elif self._x > 1:
                self._x -= 1
            elif self._y < 4:
                self._y += 1
                self._x = 1
            else:
                self._x, self._y = 1, 1
            # The firmware prints START here and again inside its grid move.
            self._sink(
                AppEvent(EventKind.GANTRY_START, "gantry", {"x": self._x, "y": self._y})
            )
            self._sink(
                AppEvent(EventKind.GANTRY_START, "gantry", {"x": self._x, "y": self._y})
            )
            self._sink(
                AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": self._x, "y": self._y})
            )
            return
        if command in ("U", "D", "L", "R"):
            self._sink(
                AppEvent(EventKind.GANTRY_RAW, "gantry", {"line": f"Moving {command}."})
            )
            return
        self._sink(
            AppEvent(EventKind.ERROR, "gantry", {"message": f"Invalid simulated command: {command}"})
        )


class MockHydroponicsController(_CommandRecorder):
    """In-memory Hydroponics Nano with a source-shaped `STAT` record."""

    def __init__(
        self,
        sink: EventSink,
        schedule_timeout: TimeoutScheduler = _schedule_timeout,
    ) -> None:
        super().__init__()
        self._sink = sink
        self._schedule_timeout = schedule_timeout
        self._status_lock = threading.RLock()
        self._water_on = False
        self._light_on = False
        self._acid_on = False
        self._fertilizer_on = False
        self._pesticide_on = False
        self._dose_time_seconds = 5.0
        self._dose_cancellations: dict[str, TimeoutCancel] = {}
        self._dose_generations = {"acid": 0, "fertilizer": 0, "pesticide": 0}

    def start(self) -> None:
        # Mirror the timestamped firmware's pump/light/dose startup outputs.
        self._cancel_dose_timeouts()
        with self._status_lock:
            self._water_on = False
            self._light_on = False
            self._acid_on = False
            self._fertilizer_on = False
            self._pesticide_on = False
            self._dose_time_seconds = 5.0
        self._started = True
        self._sink(AppEvent(EventKind.CONNECTION, "hydroponics", {"online": True}))
        self.emit_status()

    def stop(self) -> None:
        self._cancel_dose_timeouts()
        self._started = False
        self._sink(AppEvent(EventKind.CONNECTION, "hydroponics", {"online": False}))

    def send(self, command: str) -> None:
        self._record(command)
        with self._status_lock:
            if command == "WATER_PUMP:ON":
                self._water_on = True
            elif command == "WATER_PUMP:OFF":
                self._water_on = False
            elif command == "LIGHT:ON":
                self._light_on = True
            elif command == "LIGHT:OFF":
                self._light_on = False
            elif command.startswith("DOSE_TIME:"):
                try:
                    seconds = float(command.split(":", 1)[1])
                except ValueError:
                    pass
                else:
                    if seconds >= 0.0:
                        self._dose_time_seconds = seconds
        self._handle_dose_command(command)
        self._sink(AppEvent(EventKind.LOG, "hydroponics", {"message": f"Sent: {command}"}))
        self.emit_status()

    def emit_status(self) -> HydroStatus:
        with self._status_lock:
            light_on = self._light_on
            water_on = self._water_on
            acid_on = self._acid_on
            fertilizer_on = self._fertilizer_on
            pesticide_on = self._pesticide_on
        line = (
            "STAT,1000,72.5,1450.0,6.50,"
            f"{int(light_on)},{int(water_on)},{int(acid_on)},"
            f"{int(fertilizer_on)},{int(pesticide_on)}"
        )
        status = parse_hydro_status(line)
        assert status is not None
        self._sink(AppEvent(EventKind.HYDRO_RAW, "hydroponics", {"line": line}))
        self._sink(AppEvent(EventKind.HYDRO_STATUS, "hydroponics", {"status": status}))
        return status

    def _handle_dose_command(self, command: str) -> None:
        parts = command.split(":")
        if len(parts) != 3 or parts[0] != "DOSE":
            return
        dose_type = parts[1]
        try:
            millilitres = float(parts[2])
        except ValueError:
            return
        channel = {
            "ACID": "acid",
            "FERT": "fertilizer",
            "PEST": "pesticide",
        }.get(dose_type)
        if channel is None:
            return
        with self._status_lock:
            if self._dose_flag(channel):
                return
            # Manual acid/fertilizer mL maps to seconds in the legacy firmware.
            # Pesticide and non-positive values use the shared dose-time value.
            duration = (
                millilitres
                if channel != "pesticide" and millilitres > 0.0
                else self._dose_time_seconds
            )
        self._activate_dose(channel, duration)

    def _activate_dose(self, channel: str, duration: float) -> None:
        with self._status_lock:
            previous_cancel = self._dose_cancellations.pop(channel, None)
            self._dose_generations[channel] += 1
            generation = self._dose_generations[channel]
            self._set_dose_flag(channel, True)
        if previous_cancel is not None:
            previous_cancel()
        cancel = self._schedule_timeout(
            max(0.0, duration),
            lambda: self._finish_dose(channel, generation),
        )
        with self._status_lock:
            if (
                self._dose_generations[channel] == generation
                and self._dose_flag(channel)
            ):
                self._dose_cancellations[channel] = cancel
            else:
                cancel()

    def _finish_dose(self, channel: str, generation: int) -> None:
        with self._status_lock:
            if self._dose_generations[channel] != generation:
                return
            self._dose_cancellations.pop(channel, None)
            self._set_dose_flag(channel, False)
            started = self._started
        if started:
            self.emit_status()

    def _cancel_dose_timeouts(self) -> None:
        with self._status_lock:
            cancellations = tuple(self._dose_cancellations.values())
            self._dose_cancellations.clear()
            for channel in self._dose_generations:
                self._dose_generations[channel] += 1
                self._set_dose_flag(channel, False)
        for cancel in cancellations:
            cancel()

    def _dose_flag(self, channel: str) -> bool:
        return bool(getattr(self, f"_{channel}_on"))

    def _set_dose_flag(self, channel: str, enabled: bool) -> None:
        setattr(self, f"_{channel}_on", enabled)


class MockArmController:
    """Record action groups without serial imports, frames, or fixed waits."""

    def __init__(self, sink: EventSink) -> None:
        self._sink = sink
        self._groups: list[tuple[int, int]] = []
        self._lock = threading.Lock()
        self._started = False

    @property
    def groups(self) -> tuple[tuple[int, int], ...]:
        with self._lock:
            return tuple(self._groups)

    def start(self) -> None:
        self._started = True
        self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": True}))

    def stop(self) -> None:
        self._started = False
        self._sink(AppEvent(EventKind.CONNECTION, "arm", {"online": False}))

    def run_group(self, group_id: int, repeat_count: int = 1) -> None:
        if not self._started:
            raise RuntimeError("Simulated arm has not been started")
        with self._lock:
            self._groups.append((group_id, repeat_count))
        self._sink(
            AppEvent(EventKind.ARM_STATE, "arm", {"state": f"Running Group {group_id}"})
        )

    def stop_group(self) -> None:
        self._sink(AppEvent(EventKind.ARM_STATE, "arm", {"state": "Stopped"}))
