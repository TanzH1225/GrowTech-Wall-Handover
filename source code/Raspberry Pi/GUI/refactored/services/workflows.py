"""Manual arm/gantry/hydro workflows with preserved command order and waits."""

from __future__ import annotations

import time
from typing import Callable

from comm.interfaces import ArmController, GantryController, HydroponicsController
from comm.protocols import gantry_grid_command, hydro_dose_command
from config.settings import AppConfig
from domain.grid import position_for_plant
from services.events import AppEvent, EventKind
from services.state import ApplicationState
from utils.errors import GrowTechError


EventSink = Callable[[AppEvent], None]
StopPredicate = Callable[[], bool]


class WorkflowService:
    """Coordinate legacy harvest, transplant, pesticide, and arm sequences."""

    def __init__(
        self,
        config: AppConfig,
        state: ApplicationState,
        gantry: GantryController,
        hydroponics: HydroponicsController,
        arm: ArmController,
        sink: EventSink,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._state = state
        self._gantry = gantry
        self._hydroponics = hydroponics
        self._arm = arm
        self._sink = sink
        self._sleep = sleep

    def run_arm_group(self, group_id: int) -> None:
        """Send one group and preserve its fixed legacy completion assumption."""

        # No per-group Gantry refresh is performed here. This is a difference
        # from the later POS-refresh gate in the current legacy application.
        self._arm.run_group(group_id, 1)
        self._sleep(self._config.action_duration(group_id))

    def run_arm_group_interruptibly(
        self,
        group_id: int,
        stop_requested: StopPredicate,
    ) -> bool:
        """Send a group, then allow software cancellation of its assumed wait.

        Returning early cannot stop the already-sent physical arm action.
        """

        if stop_requested():
            return False
        try:
            self._arm.run_group(group_id, 1)
        except GrowTechError as exc:
            # This refactor warns and continues after an expected arm failure.
            # The current legacy GUI instead returns False from its group helper;
            # do not assume the two containing workflows now fail identically.
            self._sink(
                AppEvent(
                    EventKind.OPERATOR_NOTICE,
                    "arm",
                    {
                        "level": "warning",
                        "title": "ServoControl",
                        "message": (
                            f"Robotic arm command {group_id} was skipped because "
                            f"the arm endpoint is unavailable: {exc}"
                        ),
                    },
                )
            )
            # True means the coordinator may continue after a skipped group;
            # it is not evidence that the controller completed an arm action.
            return True
        return self._sleep_interruptibly(
            self._config.action_duration(group_id), stop_requested
        )

    def harvest(self, stop_requested: StopPredicate = lambda: False) -> None:
        """Run the legacy harvest sequence at the current grid position."""

        current = self._require_current_position()
        x, y = current
        if not self.run_arm_group_interruptibly(1, stop_requested):
            return
        if not self._sleep_interruptibly(0.5, stop_requested):
            return
        if x == 1:
            if not self._move_and_wait(2, y, stop_requested):
                return
            if not self.run_arm_group_interruptibly(2, stop_requested):
                return
            if not self._move_and_wait(1, y, stop_requested):
                return
        else:
            if not self.run_arm_group_interruptibly(2, stop_requested):
                return
        if not self._sleep_interruptibly(1.0, stop_requested):
            return
        if not self.run_arm_group_interruptibly(5, stop_requested):
            return
        self._sink(AppEvent(EventKind.ARM_STATE, "arm", {"state": "Idle"}))

    def transplant(self, stop_requested: StopPredicate = lambda: False) -> None:
        """Fetch a seedling from plant-six rack position and plant it."""

        old_x, old_y = self._require_current_position()
        rack = position_for_plant(self._config.seedling_rack_plant)
        self._move_and_wait(rack.x, rack.y, stop_requested)
        if stop_requested():
            return
        if not self.run_arm_group_interruptibly(3, stop_requested):
            return
        if not self._move_and_wait(old_x, old_y, stop_requested):
            return
        if not self.run_arm_group_interruptibly(4, stop_requested):
            return
        if not self._sleep_interruptibly(0.5, stop_requested):
            return
        if not self.run_arm_group_interruptibly(5, stop_requested):
            return
        self._sink(AppEvent(EventKind.ARM_STATE, "arm", {"state": "Idle"}))

    def pesticide(self, stop_requested: StopPredicate = lambda: False) -> None:
        """Preserve `DOSE:PEST:11`, arm group six, then idle group five."""

        if stop_requested():
            return
        # Pesticide has no _require_current_position call or fresh POS gate.
        # A successful send confirms only the write, not pump activation/duration.
        self._hydroponics.send(
            hydro_dose_command("PEST", self._config.pesticide_dose_ml)
        )
        if not self.run_arm_group_interruptibly(6, stop_requested):
            return
        if not self._sleep_interruptibly(0.5, stop_requested):
            return
        if not self.run_arm_group_interruptibly(5, stop_requested):
            return
        self._sink(AppEvent(EventKind.ARM_STATE, "arm", {"state": "Idle"}))

    def _move_and_wait(self, x: int, y: int, stop_requested: StopPredicate) -> bool:
        if stop_requested():
            return False
        # Capture the accepted-report counter before writing, so an already
        # cached coordinate alone cannot release this new move wait.
        before = self._state.snapshot().position_generation
        command = gantry_grid_command(x, y)
        self._sink(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": command, "x": x, "y": y},
            )
        )
        self._gantry.send(command)
        return self._state.wait_for_position(x, y, before, stop_requested)

    def _require_current_position(self) -> tuple[int, int]:
        snapshot = self._state.snapshot()
        if (
            not snapshot.position_valid
            or snapshot.current_x is None
            or snapshot.current_y is None
        ):
            raise GrowTechError("A fresh Gantry Nano POS report is required")
        return snapshot.current_x, snapshot.current_y

    def _sleep_interruptibly(
        self,
        seconds: float,
        stop_requested: StopPredicate,
    ) -> bool:
        remaining = max(0.0, seconds)
        while remaining > 0.0:
            if stop_requested():
                return False
            interval = min(0.1, remaining)
            self._sleep(interval)
            remaining -= interval
        return not stop_requested()
