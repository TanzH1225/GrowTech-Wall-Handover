"""Interruptible Pi coordinator for legacy scan-only and full-auto order."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Literal

from comm.interfaces import GantryController, VisionService
from comm.protocols import gantry_grid_command, gantry_home_command
from domain.grid import SNAKE_SEQUENCE, position_for_plant
from services.events import AppEvent, EventKind
from services.state import ApplicationState
from services.workflows import WorkflowService


AutomationMode = Literal["scan", "full"]
EventSink = Callable[[AppEvent], None]


class AutomationService:
    """Own a single automation worker and expose explicit state transitions."""

    def __init__(
        self,
        state: ApplicationState,
        gantry: GantryController,
        vision: VisionService,
        workflows: WorkflowService,
        sink: EventSink,
        post_capture_sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._state = state
        self._gantry = gantry
        self._vision = vision
        self._workflows = workflows
        self._sink = sink
        self._post_capture_sleep = post_capture_sleep
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("services.automation")

    @property
    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def start(self, mode: AutomationMode) -> None:
        """Start scan-only or full-auto if no automation is active."""

        if mode not in ("scan", "full"):
            raise ValueError(f"Unknown automation mode: {mode}")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("Automation is already running")
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(mode,),
                name=f"automation-{mode}",
                daemon=True,
            )
            self._thread.start()

    def request_stop(self) -> None:
        """Stop Pi orchestration at an interruptible boundary.

        This does not claim to stop an already-running Nano move or arm group.
        """

        # Serialize cancellation with start's clear-and-launch transaction so a
        # concurrent Reset/shutdown stop cannot be cleared by a late startup.
        with self._lock:
            self._stop.set()
            running = bool(self._thread and self._thread.is_alive())
        if running:
            self._transition("stopping")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the current automation worker; return whether it finished."""

        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run(self, mode: AutomationMode) -> None:
        try:
            self._transition("homing")
            before_home = self._state.snapshot()
            home_command = gantry_home_command()
            self._sink(
                AppEvent(
                    EventKind.GANTRY_REQUEST,
                    "gantry",
                    {"command": home_command},
                )
            )
            self._gantry.send(home_command)
            if not self._state.wait_for_home(
                before_home.home_generation,
                self._stop.is_set,
                after_position_generation=before_home.position_generation,
                expected_position=(1, 1),
            ):
                self._transition("stopped")
                return

            for plant in SNAKE_SEQUENCE:
                if self._stop.is_set():
                    self._transition("stopped")
                    return
                position = position_for_plant(plant)
                self._transition("moving", plant=plant)
                position_generation = self._state.snapshot().position_generation
                command = gantry_grid_command(position.x, position.y)
                self._sink(
                    AppEvent(
                        EventKind.GANTRY_REQUEST,
                        "gantry",
                        {"command": command, "x": position.x, "y": position.y},
                    )
                )
                self._gantry.send(command)
                if not self._state.wait_for_position(
                    position.x,
                    position.y,
                    position_generation,
                    self._stop.is_set,
                ):
                    self._transition("stopped")
                    return

                self._transition("capturing", plant=plant)
                result = self._vision.capture(plant)
                self._sink(
                    AppEvent(
                        EventKind.VISION_RESULT,
                        "vision",
                        {"result": result, "auto_close": True},
                    )
                )

                # Decisions use this capture result, not a widget label. The
                # case-sensitive legacy label/substrings remain policy inputs.
                if mode == "full":
                    self._transition("acting", plant=plant)
                    label = result.label
                    if label == "No detection" or "Immatured" in label:
                        self._workflows.run_arm_group_interruptibly(
                            5, self._stop.is_set
                        )
                    elif "Matured" in label:
                        self._workflows.harvest(self._stop.is_set)
                        if not self._stop.is_set():
                            self._workflows.transplant(self._stop.is_set)
                    else:
                        self._workflows.pesticide(self._stop.is_set)
                    # Preserve the legacy full-auto inter-pot action delay.
                    delay = 0.1
                else:
                    # Preserve the legacy scan-only one-second popup/capture gap.
                    delay = 1.0

                if not self._wait_post_capture(delay):
                    self._transition("stopped")
                    return

            # Complete records Pi sequence progress and assumed arm waits;
            # there is no correlated pump or arm completion acknowledgement.
            self._transition("complete")
        except Exception as exc:
            self._logger.exception("Automation failed")
            self._sink(
                AppEvent(EventKind.ERROR, "automation", {"message": str(exc)})
            )
            self._transition("failed")
        finally:
            with self._lock:
                self._thread = None

    def _transition(self, state: str, plant: int | None = None) -> None:
        data: dict[str, object] = {"state": state}
        if plant is not None:
            data["plant"] = plant
        self._sink(AppEvent(EventKind.AUTOMATION_STATE, "automation", data))

    def _wait_post_capture(self, seconds: float) -> bool:
        """Preserve the delay while checking Stop at 100-ms boundaries."""

        remaining = max(0.0, seconds)
        while remaining > 0.0:
            if self._stop.is_set():
                return False
            interval = min(0.1, remaining)
            self._post_capture_sleep(interval)
            remaining -= interval
        return not self._stop.is_set()
