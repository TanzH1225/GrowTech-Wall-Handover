"""GUI-facing application facade; every potentially blocking action is a job."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from comm.interfaces import ArmController, GantryController, HydroponicsController, VisionService
from comm.protocols import (
    gantry_grid_command,
    gantry_command_changes_position,
    hydro_dose_command,
    hydro_dose_time_command,
    hydro_light_command,
    hydro_light_hour_command,
    hydro_target_ec_command,
    hydro_target_ph_command,
    hydro_water_command,
    validate_manual_dose_ml,
)
from config.settings import AppConfig
from domain.grid import plant_for_xy
from services.automation import AutomationMode, AutomationService
from services.events import AppEvent, EventKind, UiEventQueue
from services.state import ApplicationEventRouter, ApplicationState
from services.workflows import WorkflowService
from services.worker_lane import OrderedWorkerLane
from utils.errors import GrowTechError


class ApplicationController:
    """Own all runtime services; no instance is created at module import."""

    RESET_BARRIER_TIMEOUT_SECONDS = 2.0
    SHUTDOWN_JOIN_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        config: AppConfig,
        state: ApplicationState,
        ui_events: UiEventQueue,
        router: ApplicationEventRouter,
        gantry: GantryController,
        hydroponics: HydroponicsController,
        arm: ArmController,
        vision: VisionService,
        simulation: bool,
    ) -> None:
        self.config = config
        self.state = state
        self.ui_events = ui_events
        self.simulation = simulation
        self._router = router
        self._gantry = gantry
        self._hydroponics = hydroponics
        self._arm = arm
        self._vision = vision
        # Start/stop of each provider is serialized independently. Separate
        # locks let one stuck close remain bounded without blocking cleanup of
        # unrelated endpoints.
        self._provider_lifecycle_locks = {
            "vision": threading.Lock(),
            "gantry": threading.Lock(),
            "hydroponics": threading.Lock(),
            "arm": threading.Lock(),
        }
        # FIFO order is local to each lane. Hydro commands can run while a
        # workflow waits for POS; the lanes are not a system-wide transaction.
        self._lanes = {
            "workflow": OrderedWorkerLane("workflow"),
            "hydro": OrderedWorkerLane("hydro"),
            "vision": OrderedWorkerLane("vision"),
            "reset": OrderedWorkerLane("reset"),
        }
        self._job_cancel = threading.Event()
        # Serial admission and its epoch coordinate Reset Serial with work
        # already queued on the independent workflow and Hydro lanes.
        self._serial_admission = threading.Lock()
        self._serial_epoch_lock = threading.Lock()
        self._serial_epoch = 0
        self._serial_resetting = False
        # A physical Gantry write/home boundary cannot overlap an accepted
        # camera capture selected through the workflow coordinator.
        self._gantry_capture_io = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._shutdown_started = False
        self._shutdown_done = threading.Event()
        self._logger = logging.getLogger("services.controller")
        sleeper = (lambda _seconds: None) if simulation else time.sleep
        self._workflows = WorkflowService(
            config,
            state,
            gantry,
            hydroponics,
            arm,
            router.publish,
            sleep=sleeper,
        )
        self._automation = AutomationService(
            state,
            gantry,
            vision,
            self._workflows,
            router.publish,
            post_capture_sleep=sleeper,
        )
        self._started = False

    @property
    def automation_running(self) -> bool:
        return self._automation.is_running

    def start(self) -> None:
        """Explicitly initialize configured services, retaining offline GUI use."""

        with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Application controller has already been shut down")
            if self._started:
                return
        # Preserve the legacy startup order: model/camera, native arm UART,
        # Gantry Nano (including its settle/reset), then Hydroponics Nano.
        for name, service in (
            ("vision", self._vision),
            ("arm", self._arm),
            ("gantry", self._gantry),
            ("hydroponics", self._hydroponics),
        ):
            try:
                with self._provider_lifecycle_locks[name]:
                    if self._job_cancel.is_set():
                        raise RuntimeError(
                            "Application shutdown started during provider startup"
                        )
                    service.start()
                if name == "vision":
                    self._router.publish(
                        AppEvent(EventKind.CONNECTION, "vision", {"online": True})
                    )
            except Exception as exc:
                self._logger.exception("Could not start %s", name)
                self._router.publish(
                    AppEvent(EventKind.CONNECTION, name, {"online": False})
                )
                self._router.publish(
                    AppEvent(EventKind.ERROR, name, {"message": str(exc)})
                )
        self._started = True

    def submit(
        self,
        name: str,
        action: Callable[[], object],
        lane: str = "workflow",
    ) -> bool:
        """Run a blocking service call off the Tk thread and report errors."""

        def job() -> None:
            try:
                action()
            except Exception as exc:
                self._logger.exception("%s failed", name)
                self._router.publish(
                    AppEvent(EventKind.ERROR, name, {"message": str(exc)})
                )

        with self._lifecycle_lock:
            if self._shutdown_started:
                self._router.publish(
                    AppEvent(EventKind.ERROR, name, {"message": "Application is shutting down"})
                )
                return False
            worker = self._lanes.get(lane)
            if worker is None:
                raise ValueError(f"Unknown worker lane: {lane}")
            accepted = worker.submit(job)
        if not accepted:
            self._router.publish(
                AppEvent(EventKind.ERROR, name, {"message": f"{lane} lane is closed"})
            )
        return accepted

    def send_gantry(self, command: str) -> None:
        changes_position = gantry_command_changes_position(command)
        target = self._grid_target(command)
        with self._serial_admission:
            if self._serial_resetting:
                self._reset_in_progress_error("gantry")
                return
            epoch = self._current_serial_epoch()

            def send() -> None:
                if self._epoch_cancelled(epoch):
                    return
                if self.automation_running:
                    raise GrowTechError(
                        "Manual Gantry command rejected while automation is running"
                    )
                with self._gantry_capture_io:
                    if self._epoch_cancelled(epoch):
                        return
                    if changes_position:
                        self._publish_gantry_request(command)
                    snapshot = self.state.snapshot()
                    position_before = snapshot.position_generation
                    home_before = snapshot.home_generation
                    self._gantry.send(command)
                stop_requested = lambda: self._epoch_cancelled(epoch)
                # Only grid, Next, and Home have report-based ordering fences.
                # Relative commands emit no POS and return after the write.
                if target is not None:
                    self.state.wait_for_position(
                        target[0], target[1], position_before, stop_requested
                    )
                elif command.strip().upper() == "G":
                    # The target is learned from START/POS, but a second G
                    # must not be written until the first fresh POS arrives.
                    self.state.wait_for_any_position(position_before, stop_requested)
                elif command.strip() == "0 0":
                    self.state.wait_for_home(
                        home_before,
                        stop_requested,
                        after_position_generation=position_before,
                        expected_position=(1, 1),
                    )

            self.submit("gantry", send)

    def move_to(self, x: int, y: int) -> None:
        self.send_gantry(gantry_grid_command(x, y))

    def send_hydroponics(self, command: str) -> None:
        self._submit_serial_operation(
            "hydroponics",
            lambda _epoch: self._hydroponics.send(command),
            lane="hydro",
        )

    def set_water(self, enabled: bool) -> None:
        self.send_hydroponics(hydro_water_command(enabled))

    def set_light(self, enabled: bool) -> None:
        self.send_hydroponics(hydro_light_command(enabled))

    def dose(self, kind: str, millilitres: int) -> None:
        validate_manual_dose_ml(millilitres)
        self.send_hydroponics(hydro_dose_command(kind, millilitres))

    def set_ec_target(self, value: float) -> None:
        self.send_hydroponics(hydro_target_ec_command(value))

    def set_ph_target(self, value: float) -> None:
        self.send_hydroponics(hydro_target_ph_command(value))

    def set_dose_time(self, millilitres: int) -> None:
        self.send_hydroponics(hydro_dose_time_command(millilitres))

    def set_light_schedule(self, on_hour: int, off_hour: int) -> None:
        commands = hydro_light_hour_command(on_hour, off_hour)

        def send_schedule(epoch: int) -> None:
            for command in commands:
                if self._epoch_cancelled(epoch):
                    return
                self._hydroponics.send(command)

        self._submit_serial_operation(
            "hydroponics schedule",
            send_schedule,
            lane="hydro",
        )

    def run_arm_group(self, group_id: int) -> None:
        self._submit_serial_operation(
            "arm",
            lambda epoch: self._workflows.run_arm_group_interruptibly(
                group_id, lambda: self._epoch_cancelled(epoch)
            ),
        )

    def harvest(self) -> None:
        if not self._require_valid_position("harvest"):
            return
        self._submit_serial_operation(
            "harvest",
            lambda epoch: self._run_exclusive_workflow(
                "Harvest",
                lambda: self._workflows.harvest(
                    lambda: self._epoch_cancelled(epoch)
                ),
            ),
        )

    def transplant(self) -> None:
        if not self._require_valid_position("transplant"):
            return
        self._submit_serial_operation(
            "transplant",
            lambda epoch: self._run_exclusive_workflow(
                "Transplant",
                lambda: self._workflows.transplant(
                    lambda: self._epoch_cancelled(epoch)
                ),
            ),
        )

    # Unlike harvest/transplant, this entry point has no position-validity gate.
    # Current legacy GTW_GUIv2.py re-confirms a POS before dosing; this parallel
    # implementation does not yet contain that later legacy refresh boundary.
    def pesticide(self) -> None:
        self._submit_serial_operation(
            "pesticide",
            lambda epoch: self._run_exclusive_workflow(
                "Pesticide",
                lambda: self._workflows.pesticide(
                    lambda: self._epoch_cancelled(epoch)
                ),
            ),
        )

    def capture_current(self) -> None:
        """Capture the plant at the last reported grid position."""

        snapshot = self.state.snapshot()
        if not snapshot.position_valid:
            self._position_required_error("vision")
            return

        def coordinate_capture(epoch: int) -> None:
            current = self.state.snapshot()
            if (
                not current.position_valid
                or current.current_x is None
                or current.current_y is None
            ):
                raise GrowTechError("A fresh Gantry Nano POS report is required")
            plant = plant_for_xy(current.current_x, current.current_y)
            if plant is None:
                raise GrowTechError("Current gantry coordinate is not a plant position")
            position_generation = current.position_generation
            completed = threading.Event()

            def capture() -> None:
                try:
                    if self._epoch_cancelled(epoch):
                        return
                    with self._gantry_capture_io:
                        if self._epoch_cancelled(epoch):
                            return
                        latest = self.state.snapshot()
                        if (
                            not latest.position_valid
                            or latest.position_generation != position_generation
                            or latest.current_x != current.current_x
                            or latest.current_y != current.current_y
                        ):
                            raise GrowTechError(
                                "Gantry position changed before vision capture"
                            )
                        result = self._vision.capture(plant)
                    self._router.publish(
                        AppEvent(
                            EventKind.VISION_RESULT,
                            "vision",
                            {"result": result, "auto_close": False},
                        )
                    )
                finally:
                    completed.set()

            if not self.submit("vision", capture, lane="vision"):
                return
            # Keep the workflow lane at this ordering fence. A move submitted
            # after Capture cannot be written while the camera operation runs.
            while not completed.wait(timeout=0.1):
                if self._job_cancel.is_set():
                    return

        self._submit_serial_operation("vision", coordinate_capture)

    def start_automation(self, mode: AutomationMode) -> None:
        # Starting through the workflow lane preserves click order with an
        # already-queued manual move or capture; the automation then owns its
        # separate long-running coordinator thread.
        self._submit_serial_operation(
            "automation",
            lambda _epoch: self._automation.start(mode),
        )

    def stop_automation(self) -> None:
        self._automation.request_stop()

    def reset_serial(self) -> None:
        """Reopen vision and both Nano endpoints after bounded quiescence.

        The public method name is retained for compatibility with the existing
        GUI callback.  Reopening the Gantry Nano still retains the legacy
        reset/home risk.
        """

        workflow_barrier = threading.Event()
        hydro_barrier = threading.Event()
        vision_barrier = threading.Event()

        def reset() -> None:
            results: list[str] = []
            try:
                self._automation.request_stop()
                deadline = time.monotonic() + self.RESET_BARRIER_TIMEOUT_SECONDS
                # Start daemon-owned closes first so blocked serial operations
                # can unwind, without allowing a stuck close to retain Reset.
                stop_operations = self._begin_provider_stops(
                    (
                        ("gantry", self._gantry.stop),
                        ("hydroponics", self._hydroponics.stop),
                    ),
                    error_prefix="Reset close failed",
                    publish_errors=True,
                )
                stop_ready = {
                    name: self._wait_for_event(done, deadline)
                    for name, done in stop_operations.items()
                }
                automation_ready = self._automation.wait(
                    timeout=max(0.0, deadline - time.monotonic())
                )
                workflow_ready = self._wait_for_event(workflow_barrier, deadline)
                hydro_ready = self._wait_for_event(hydro_barrier, deadline)
                vision_ready = self._wait_for_event(vision_barrier, deadline)

                # Do not release a camera while capture/inference may still be
                # using it.  Once automation and both coordinating lanes have
                # quiesced, close vision under the same bounded reset policy as
                # the serial providers.
                vision_quiesced = (
                    automation_ready and workflow_ready and vision_ready
                )
                vision_stop_ready = False
                if vision_quiesced:
                    vision_stops = self._begin_provider_stops(
                        (("vision", self._vision.stop),),
                        error_prefix="Reset close failed",
                        publish_errors=True,
                    )
                    vision_stop_ready = self._wait_for_event(
                        vision_stops["vision"], deadline
                    )
                    if vision_stop_ready:
                        self._router.publish(
                            AppEvent(
                                EventKind.CONNECTION,
                                "vision",
                                {"online": False},
                            )
                        )
                else:
                    results.append("vision: unchanged")
                    self._router.publish(
                        AppEvent(
                            EventKind.ERROR,
                            "vision",
                            {
                                "message":
                                "Reset left camera unchanged because prior vision "
                                "work did not quiesce before the bounded deadline"
                            },
                        )
                    )

                readiness: list[tuple[str, object, bool]] = []
                if vision_quiesced:
                    readiness.append(
                        (
                            "vision",
                            self._vision,
                            vision_stop_ready,
                        )
                    )
                readiness.extend(
                    (
                        (
                            "gantry",
                            self._gantry,
                            stop_ready["gantry"]
                            and workflow_ready
                            and automation_ready,
                        ),
                        (
                            "hydroponics",
                            self._hydroponics,
                            stop_ready["hydroponics"]
                            and hydro_ready
                            and automation_ready,
                        ),
                    )
                )
                # The shared deadline bounds quiescence and close waits. A ready
                # provider start still includes its configured startup settling.
                for name, service, ready in readiness:
                    if self._job_cancel.is_set():
                        results.append(f"{name}: reset cancelled")
                        continue
                    if not ready:
                        results.append(f"{name}: offline")
                        self._router.publish(
                            AppEvent(
                                EventKind.CONNECTION,
                                name,
                                {"online": False},
                            )
                        )
                        self._router.publish(
                            AppEvent(
                                EventKind.ERROR,
                                name,
                                {
                                    "message":
                                    "Reset left endpoint offline because its close or "
                                    "prior work did not quiesce before the bounded deadline"
                                },
                            )
                        )
                        continue
                    try:
                        with self._provider_lifecycle_locks[name]:
                            # Shutdown may have begun after the readiness check.
                            # Recheck while serialized with its matching close:
                            # either reopen finishes then shutdown closes it, or
                            # shutdown closes first and this reopen is skipped.
                            if self._job_cancel.is_set():
                                results.append(f"{name}: reset cancelled")
                                continue
                            if name == "gantry":
                                # Reassert the reset blocker after all stale
                                # queued jobs/reports, then serialize reopen/home
                                # with any accepted capture boundary.
                                self._publish_gantry_request("serial reset")
                                with self._gantry_capture_io:
                                    service.start()
                            else:
                                service.start()
                            if name == "vision":
                                self._router.publish(
                                    AppEvent(
                                        EventKind.CONNECTION,
                                        "vision",
                                        {"online": True},
                                    )
                                )
                        results.append(f"{name}: online")
                    except Exception as exc:
                        results.append(f"{name}: offline")
                        self._router.publish(
                            AppEvent(EventKind.CONNECTION, name, {"online": False})
                        )
                        self._router.publish(
                            AppEvent(
                                EventKind.ERROR,
                                name,
                                {"message": f"Reset open failed: {exc}"},
                            )
                        )
                self._router.publish(
                    AppEvent(EventKind.LOG, "system", {"message": "; ".join(results)})
                )
                self._router.publish(
                    AppEvent(
                        EventKind.OPERATOR_NOTICE,
                        "connection reset",
                        {
                            "level": "info",
                            "title": "Connection Reset",
                            "message": "Camera and serial connections have been reset.",
                        },
                    )
                )
            finally:
                with self._serial_admission:
                    self._serial_resetting = False
                self._publish_operation_state("Device Reset", False)

        # Admission establishes one enqueue order: every earlier endpoint job,
        # then the three barriers, while later submissions reject until reopen.
        with self._serial_admission:
            if self._serial_resetting:
                self._router.publish(
                    AppEvent(
                        EventKind.LOG,
                        "system",
                        {"message": "Device reset is already in progress"},
                    )
                )
                return
            self._serial_resetting = True
            self._publish_operation_state("Device Reset", True)
            with self._serial_epoch_lock:
                self._serial_epoch += 1
            self._publish_gantry_request("serial reset")
            self.state.wake_waiters()
            workflow_queued = self._lanes["workflow"].submit(
                workflow_barrier.set
            )
            hydro_queued = self._lanes["hydro"].submit(hydro_barrier.set)
            vision_queued = self._lanes["vision"].submit(vision_barrier.set)
            if not workflow_queued or not hydro_queued or not vision_queued:
                self._serial_resetting = False
                self._publish_operation_state("Device Reset", False)
                self._router.publish(
                    AppEvent(
                        EventKind.ERROR,
                        "serial reset",
                        {"message": "Could not queue reset barriers during shutdown"},
                    )
                )
                return
            accepted = self.submit("serial reset", reset, lane="reset")
            if not accepted:
                self._serial_resetting = False
                self._publish_operation_state("Device Reset", False)

    def shutdown(self) -> None:
        """Cancel Pi work and release resources; safe to call repeatedly.

        Cancellation releases software waits and fixed-duration assumptions. It
        does not stop a gantry move or robotic-arm action already sent to a
        physical controller; that limitation still requires operator handling.
        """

        with self._lifecycle_lock:
            if self._shutdown_started:
                already_running = True
            else:
                self._shutdown_started = True
                already_running = False
        if already_running:
            self._shutdown_done.wait(
                timeout=self.SHUTDOWN_JOIN_TIMEOUT_SECONDS + 0.5
            )
            return

        try:
            self._job_cancel.set()
            self.state.wake_waiters()
            self._automation.request_stop()
            for lane in self._lanes.values():
                lane.close(cancel_pending=True)
            deadline = time.monotonic() + self.SHUTDOWN_JOIN_TIMEOUT_SECONDS
            # Daemon-owned provider closes begin before joins so I/O can
            # unblock, while one stuck third-party close cannot retain exit.
            # Arm.stop closes the UART transport; shutdown does not invoke
            # Arm.stop_group or transmit the binary action-group-stop frame.
            stop_operations = self._begin_provider_stops(
                (
                    ("vision", self._vision.stop),
                    ("gantry", self._gantry.stop),
                    ("hydroponics", self._hydroponics.stop),
                    ("arm", self._arm.stop),
                ),
                error_prefix="Service shutdown failed",
            )
            self._automation.wait(timeout=max(0.0, deadline - time.monotonic()))
            for name, lane in self._lanes.items():
                remaining = max(0.0, deadline - time.monotonic())
                if not lane.join(remaining):
                    self._logger.warning(
                        "%s worker remains blocked after bounded shutdown; "
                        "daemon ownership prevents interpreter retention",
                        name,
                    )
            for name, done in stop_operations.items():
                if not done.wait(timeout=max(0.0, deadline - time.monotonic())):
                    self._logger.warning(
                        "%s provider close remains blocked after bounded shutdown; "
                        "daemon ownership prevents interpreter retention",
                        name,
                    )
            self._started = False
        finally:
            self._shutdown_done.set()

    def _submit_serial_operation(
        self,
        name: str,
        action: Callable[[int], object],
        lane: str = "workflow",
    ) -> bool:
        """Admit one reset-cancellable endpoint/workflow operation in order."""

        with self._serial_admission:
            if self._serial_resetting:
                self._reset_in_progress_error(name)
                return False
            epoch = self._current_serial_epoch()

            def guarded() -> object | None:
                if self._epoch_cancelled(epoch):
                    return None
                if lane == "workflow" and name != "automation" and self.automation_running:
                    raise GrowTechError(
                        f"{name} rejected while automation is running"
                    )
                return action(epoch)

            return self.submit(name, guarded, lane=lane)

    def _epoch_cancelled(self, epoch: int) -> bool:
        if self._job_cancel.is_set():
            return True
        with self._serial_epoch_lock:
            return epoch != self._serial_epoch

    def _current_serial_epoch(self) -> int:
        with self._serial_epoch_lock:
            return self._serial_epoch

    def _wait_for_event(self, event: threading.Event, deadline: float) -> bool:
        """Wait for a reset barrier without extending its shared deadline."""

        while not event.is_set() and not self._job_cancel.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            event.wait(timeout=min(0.05, remaining))
        return event.is_set()

    def _begin_provider_stops(
        self,
        services: tuple[tuple[str, Callable[[], object]], ...],
        *,
        error_prefix: str,
        publish_errors: bool = False,
    ) -> dict[str, threading.Event]:
        """Start provider closes on daemon threads and return completion events.

        Serial drivers, camera backends, and injected implementations are not
        trusted to return from ``stop()``. Callers apply one shared deadline to
        these events and their worker barriers, so reset and shutdown stay
        bounded without reopening an endpoint beside an in-progress close.
        """

        operations: dict[str, threading.Event] = {}
        for name, stop in services:
            completed = threading.Event()
            operations[name] = completed

            def close_provider(
                provider_name: str = name,
                provider_stop: Callable[[], object] = stop,
                done: threading.Event = completed,
            ) -> None:
                try:
                    with self._provider_lifecycle_locks[provider_name]:
                        provider_stop()
                except Exception as exc:
                    self._logger.exception("%s for %s", error_prefix, provider_name)
                    if publish_errors:
                        self._router.publish(
                            AppEvent(
                                EventKind.ERROR,
                                provider_name,
                                {"message": f"{error_prefix}: {exc}"},
                            )
                        )
                finally:
                    done.set()

            threading.Thread(
                target=close_provider,
                name=f"growtech-close-{name}",
                daemon=True,
            ).start()
        return operations

    def _reset_in_progress_error(self, source: str) -> None:
        self._router.publish(
            AppEvent(
                EventKind.ERROR,
                source,
                {"message": "Serial reset is in progress; command was not queued"},
            )
        )

    def _run_exclusive_workflow(
        self,
        name: str,
        action: Callable[[], object],
    ) -> None:
        """Expose manual workflow exclusivity to the GUI while it runs."""

        self._publish_operation_state(name, True)
        try:
            action()
        except Exception:
            self._publish_operation_state(name, False, outcome="failed")
            raise
        else:
            self._publish_operation_state(name, False, outcome="complete")

    def _publish_operation_state(
        self,
        name: str,
        running: bool,
        *,
        outcome: str | None = None,
    ) -> None:
        data: dict[str, object] = {"operation": name, "running": running}
        if outcome is not None:
            data["outcome"] = outcome
        self._router.publish(
            AppEvent(
                EventKind.OPERATION_STATE,
                name.lower(),
                data,
            )
        )

    def _publish_gantry_request(self, command: str) -> None:
        data: dict[str, object] = {"command": command}
        parts = command.split()
        if len(parts) == 2:
            try:
                x, y = int(parts[0]), int(parts[1])
            except ValueError:
                pass
            else:
                if 1 <= x <= 6 and 1 <= y <= 4:
                    data.update({"x": x, "y": y})
        self._router.publish(AppEvent(EventKind.GANTRY_REQUEST, "gantry", data))

    @staticmethod
    def _grid_target(command: str) -> tuple[int, int] | None:
        parts = command.split()
        if len(parts) != 2:
            return None
        try:
            x, y = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        return (x, y) if 1 <= x <= 6 and 1 <= y <= 4 else None

    def _require_valid_position(self, operation: str) -> bool:
        if self.state.snapshot().position_valid:
            return True
        self._position_required_error(operation)
        return False

    def _position_required_error(self, source: str) -> None:
        self._router.publish(
            AppEvent(
                EventKind.ERROR,
                source,
                {"message": "A fresh Gantry Nano POS report is required"},
            )
        )
