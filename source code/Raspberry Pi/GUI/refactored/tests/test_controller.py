from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_controller
from config.settings import AppConfig
from domain.models import VisionResult
from services.controller import ApplicationController
from services.events import AppEvent, EventKind, UiEventQueue
from services.state import ApplicationEventRouter, ApplicationState


class Endpoint:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.groups: list[int] = []
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        self.starts += 1

    def stop(self) -> None:
        self.stops += 1

    def send(self, command: str) -> None:
        self.commands.append(command)

    def run_group(self, group_id: int, repeat_count: int = 1) -> None:
        self.groups.append(group_id)

    def stop_group(self) -> None:
        pass

    def capture(self, plant: int) -> VisionResult:
        return VisionResult(plant, "No detection", None, None)


def build_controller(
    gantry: Endpoint | None = None,
    hydro: Endpoint | None = None,
    arm: Endpoint | None = None,
    vision: Endpoint | None = None,
) -> tuple[ApplicationController, ApplicationEventRouter]:
    state = ApplicationState()
    events = UiEventQueue()
    router = ApplicationEventRouter(state, events)
    controller = ApplicationController(
        AppConfig(),
        state,
        events,
        router,
        gantry or Endpoint(),
        hydro or Endpoint(),
        arm or Endpoint(),
        vision or Endpoint(),
        simulation=True,
    )
    return controller, router


class ControllerCoordinationTests(unittest.TestCase):
    def test_exclusive_workflow_publishes_visible_busy_and_completion_states(self) -> None:
        controller, _router = build_controller()
        controller.start()
        controller.ui_events.drain()
        controller.pesticide()
        finished = threading.Event()
        controller.submit("fixture marker", finished.set)
        self.assertTrue(finished.wait(timeout=1.0))
        operation_events = [
            event
            for event in controller.ui_events.drain()
            if event.kind is EventKind.OPERATION_STATE
        ]
        controller.shutdown()

        self.assertEqual(
            [event.data["running"] for event in operation_events], [True, False]
        )
        self.assertEqual(operation_events[-1].data["outcome"], "complete")

    def test_grid_request_write_and_matching_pos_stay_ordered(self) -> None:
        timeline: list[str] = []
        state = ApplicationState()
        events = UiEventQueue()

        class RecordingRouter(ApplicationEventRouter):
            def publish(self, event: AppEvent) -> None:
                timeline.append(f"event:{event.kind.value}")
                super().publish(event)

        router = RecordingRouter(state, events)

        class ControlledGantry(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.written = threading.Event()

            def send(self, command: str) -> None:
                self.commands.append(command)
                timeline.append(f"write:{command}")
                self.written.set()

            def complete(self, x: int, y: int) -> None:
                router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": x, "y": y}))
                router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": x, "y": y}))

        gantry = ControlledGantry()
        controller = ApplicationController(
            AppConfig(),
            state,
            events,
            router,
            gantry,
            Endpoint(),
            Endpoint(),
            Endpoint(),
            simulation=True,
        )
        controller.start()
        timeline.clear()
        controller.move_to(1, 1)
        self.assertTrue(gantry.written.wait(timeout=1.0))
        controller.move_to(2, 1)
        gantry.complete(1, 1)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(gantry.commands) < 2:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["1 1", "2 1"])
        # The second request invalidates the first confirmed position when its
        # own ordered job reaches the write boundary.
        self.assertFalse(state.snapshot().position_valid)
        gantry.complete(2, 1)
        finished = threading.Event()
        controller.submit("fixture marker", finished.set)
        self.assertTrue(finished.wait(timeout=1.0))
        controller.shutdown()
        self.assertTrue(state.snapshot().position_valid)
        first_request = timeline.index("event:gantry.request")
        first_write = timeline.index("write:1 1")
        first_start = timeline.index("event:gantry.start")
        first_pos = timeline.index("event:gantry.position")
        self.assertLess(first_request, first_write)
        self.assertLess(first_write, first_start)
        self.assertLess(first_start, first_pos)

    def test_capture_harvest_and_transplant_reject_stale_position(self) -> None:
        gantry, arm, vision = Endpoint(), Endpoint(), Endpoint()
        controller, _router = build_controller(gantry=gantry, arm=arm, vision=vision)
        controller.start()
        controller.ui_events.drain()
        controller.capture_current()
        controller.harvest()
        controller.transplant()
        errors = [
            event
            for event in controller.ui_events.drain()
            if event.kind is EventKind.ERROR
        ]
        controller.shutdown()
        self.assertEqual(len(errors), 3)
        self.assertTrue(all("fresh Gantry Nano POS" in str(e.data["message"]) for e in errors))
        self.assertEqual(vision.commands, [])
        self.assertEqual(arm.groups, [])
        self.assertEqual(gantry.commands, [])

    def test_manual_capture_event_is_persistent_popup_context(self) -> None:
        controller = create_controller(AppConfig(), simulate=True)
        controller.start()
        controller.ui_events.drain()
        controller.move_to(2, 2)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not controller.state.snapshot().position_valid:
            time.sleep(0.005)
        controller.ui_events.drain()
        controller.capture_current()
        result_event = None
        while time.monotonic() < deadline:
            for event in controller.ui_events.drain():
                if event.kind is EventKind.VISION_RESULT:
                    result_event = event
                    break
            if result_event is not None:
                break
            time.sleep(0.005)
        controller.shutdown()
        self.assertIsNotNone(result_event)
        assert result_event is not None
        self.assertFalse(bool(result_event.data["auto_close"]))

    def test_gui_jobs_and_two_schedule_commands_remain_ordered(self) -> None:
        hydro = Endpoint()
        controller, _router = build_controller(hydro=hydro)
        controller.start()
        controller.set_water(True)
        controller.set_light_schedule(7, 19)
        controller.set_light(False)
        finished = threading.Event()
        controller.submit("fixture marker", finished.set, lane="hydro")
        self.assertTrue(finished.wait(timeout=1.0))
        controller.shutdown()
        self.assertEqual(
            hydro.commands,
            [
                "WATER_PUMP:ON",
                "LIGHT_ON_HOUR:7",
                "LIGHT_OFF_HOUR:19",
                "LIGHT:OFF",
            ],
        )

    def test_stalled_gantry_does_not_block_hydro_lane(self) -> None:
        gantry = Endpoint()
        hydro = Endpoint()
        controller, _router = build_controller(gantry=gantry, hydro=hydro)
        controller.start()
        controller.move_to(1, 1)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["1 1"])
        controller.set_water(True)
        hydro_done = threading.Event()
        controller.submit("hydro marker", hydro_done.set, lane="hydro")
        self.assertTrue(hydro_done.wait(timeout=1.0))
        self.assertEqual(hydro.commands, ["WATER_PUMP:ON"])
        controller.shutdown()

    def test_double_next_waits_for_each_fresh_position(self) -> None:
        gantry = Endpoint()
        controller, router = build_controller(gantry=gantry)
        controller.start()
        controller.send_gantry("G")
        controller.send_gantry("G")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["G"])
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        while time.monotonic() < deadline and len(gantry.commands) < 2:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["G", "G"])
        self.assertFalse(controller.state.snapshot().position_valid)
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 1}))
        finished = threading.Event()
        controller.submit("workflow marker", finished.set)
        self.assertTrue(finished.wait(timeout=1.0))
        self.assertEqual(
            (
                controller.state.snapshot().current_x,
                controller.state.snapshot().current_y,
            ),
            (2, 1),
        )
        controller.shutdown()

    def test_reset_cancels_wait_drops_queued_move_and_reuses_lane(self) -> None:
        gantry = Endpoint()
        hydro = Endpoint()
        vision = Endpoint()
        controller, router = build_controller(
            gantry=gantry, hydro=hydro, vision=vision
        )
        controller.start()
        controller.move_to(1, 1)
        controller.move_to(2, 2)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["1 1"])
        controller.reset_serial()
        reset_done = threading.Event()
        controller.submit("reset marker", reset_done.set, lane="reset")
        self.assertTrue(reset_done.wait(timeout=1.0))
        self.assertEqual(gantry.commands, ["1 1"])
        self.assertEqual(gantry.starts, 2)
        self.assertEqual(vision.stops, 1)
        self.assertEqual(vision.starts, 2)
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 1, "y": 1}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        self.assertFalse(controller.state.snapshot().position_valid)

        controller.move_to(3, 3)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(gantry.commands) < 2:
            time.sleep(0.005)
        self.assertEqual(gantry.commands[-1], "3 3")
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 3, "y": 3}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 3, "y": 3}))
        workflow_done = threading.Event()
        controller.submit("workflow marker", workflow_done.set)
        self.assertTrue(workflow_done.wait(timeout=1.0))
        snapshot = controller.state.snapshot()
        self.assertTrue(snapshot.position_valid)
        self.assertEqual((snapshot.current_x, snapshot.current_y), (3, 3))
        controller.shutdown()

    def test_move_capture_move_interleaving_honours_workflow_order(self) -> None:
        class RecordingVision(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.captures: list[int] = []

            def capture(self, plant: int) -> VisionResult:
                self.captures.append(plant)
                return VisionResult(plant, "No detection", None, None)

        gantry = Endpoint()
        vision = RecordingVision()
        controller, router = build_controller(gantry=gantry, vision=vision)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        gate = threading.Event()
        controller.submit("fixture gate", lambda: gate.wait(timeout=1.0))

        controller.move_to(2, 2)
        controller.capture_current()
        controller.move_to(3, 2)
        gate.set()

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["2 2"])
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 2, "y": 2}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 2}))

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(gantry.commands) < 2:
            time.sleep(0.005)
        self.assertEqual(vision.captures, [8])
        self.assertEqual(gantry.commands, ["2 2", "3 2"])
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 3, "y": 2}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 3, "y": 2}))
        controller.shutdown()

    def test_move_submitted_before_capture_uses_new_position(self) -> None:
        class RecordingVision(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.captures: list[int] = []

            def capture(self, plant: int) -> VisionResult:
                self.captures.append(plant)
                return VisionResult(plant, "No detection", None, None)

        gantry = Endpoint()
        vision = RecordingVision()
        controller, router = build_controller(gantry=gantry, vision=vision)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        gate = threading.Event()
        controller.submit("fixture gate", lambda: gate.wait(timeout=1.0))
        controller.move_to(2, 2)
        controller.capture_current()
        gate.set()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(gantry.commands, ["2 2"])
        self.assertEqual(vision.captures, [])
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 2, "y": 2}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 2}))
        finished = threading.Event()
        controller.submit("workflow marker", finished.set)
        self.assertTrue(finished.wait(timeout=1.0))
        self.assertEqual(vision.captures, [8])
        controller.shutdown()

    def test_move_submitted_during_capture_waits_for_capture(self) -> None:
        class BlockingVision(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.entered = threading.Event()
                self.release = threading.Event()
                self.captures: list[int] = []

            def capture(self, plant: int) -> VisionResult:
                self.captures.append(plant)
                self.entered.set()
                self.release.wait(timeout=2.0)
                return VisionResult(plant, "No detection", None, None)

        gantry = Endpoint()
        vision = BlockingVision()
        controller, router = build_controller(gantry=gantry, vision=vision)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        controller.capture_current()
        self.assertTrue(vision.entered.wait(timeout=1.0))
        controller.move_to(2, 2)
        time.sleep(0.05)
        self.assertEqual(gantry.commands, [])
        vision.release.set()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not gantry.commands:
            time.sleep(0.005)
        self.assertEqual(vision.captures, [1])
        self.assertEqual(gantry.commands, ["2 2"])
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 2, "y": 2}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 2}))
        controller.shutdown()

    def test_reset_does_not_restart_gantry_during_active_capture(self) -> None:
        class BlockingVision(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.entered = threading.Event()
                self.release = threading.Event()

            def capture(self, plant: int) -> VisionResult:
                self.entered.set()
                self.release.wait(timeout=2.0)
                return VisionResult(plant, "No detection", None, None)

        gantry = Endpoint()
        vision = BlockingVision()
        controller, router = build_controller(gantry=gantry, vision=vision)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        controller.capture_current()
        self.assertTrue(vision.entered.wait(timeout=1.0))
        controller.reset_serial()
        time.sleep(0.05)
        self.assertEqual(gantry.starts, 1)
        self.assertEqual(vision.starts, 1)
        self.assertEqual(vision.stops, 0)
        vision.release.set()
        reset_done = threading.Event()
        controller.submit("reset marker", reset_done.set, lane="reset")
        self.assertTrue(reset_done.wait(timeout=1.0))
        self.assertEqual(gantry.starts, 2)
        self.assertEqual(vision.stops, 1)
        self.assertEqual(vision.starts, 2)
        controller.shutdown()

    def test_reset_attempts_hydro_after_gantry_close_and_open_failures(self) -> None:
        class FailingResetGantry(Endpoint):
            def start(self) -> None:
                self.starts += 1
                if self.starts > 1:
                    raise RuntimeError("gantry open fixture failure")

            def stop(self) -> None:
                self.stops += 1
                if self.stops == 1:
                    raise RuntimeError("gantry close fixture failure")

        gantry = FailingResetGantry()
        hydro = Endpoint()
        controller, router = build_controller(gantry=gantry, hydro=hydro)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 2}))
        self.assertTrue(controller.state.snapshot().position_valid)
        with self.assertLogs("services.controller", level="ERROR"):
            controller.reset_serial()
            finished = threading.Event()
            controller.submit("fixture marker", finished.set, lane="reset")
            self.assertTrue(finished.wait(timeout=1.0))
        self.assertFalse(controller.state.snapshot().position_valid)
        reset_events = controller.ui_events.drain()
        controller.shutdown()
        self.assertEqual(gantry.starts, 2)
        self.assertGreaterEqual(hydro.starts, 2)
        self.assertTrue(
            any(
                event.kind is EventKind.CONNECTION
                and event.source == "gantry"
                and not event.data.get("online")
                for event in reset_events
            )
        )

    def test_waiting_manual_workflow_exits_during_idempotent_shutdown(self) -> None:
        gantry, arm = Endpoint(), Endpoint()
        controller, router = build_controller(gantry=gantry, arm=arm)
        controller.start()
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        controller.harvest()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and "2 1" not in gantry.commands:
            time.sleep(0.005)
        self.assertIn("2 1", gantry.commands)
        started = time.monotonic()
        controller.shutdown()
        elapsed = time.monotonic() - started
        controller.shutdown()
        self.assertLess(elapsed, 1.0)
        self.assertEqual(arm.groups, [1])

    def test_non_cancellable_worker_cannot_retain_shutdown_indefinitely(self) -> None:
        controller, _router = build_controller()
        controller.SHUTDOWN_JOIN_TIMEOUT_SECONDS = 0.2
        controller.start()
        entered = threading.Event()
        release = threading.Event()

        def blocked_io() -> None:
            entered.set()
            release.wait(timeout=2.0)

        controller.submit("blocked fixture", blocked_io, lane="vision")
        self.assertTrue(entered.wait(timeout=1.0))
        started = time.monotonic()
        with self.assertLogs("services.controller", level="WARNING"):
            controller.shutdown()
        elapsed = time.monotonic() - started
        release.set()
        self.assertLess(elapsed, 0.6)

    def test_blocking_provider_close_cannot_retain_shutdown(self) -> None:
        class BlockingStopEndpoint(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.entered = threading.Event()
                self.release = threading.Event()

            def stop(self) -> None:
                self.stops += 1
                self.entered.set()
                self.release.wait()

        vision = BlockingStopEndpoint()
        controller, _router = build_controller(vision=vision)
        controller.SHUTDOWN_JOIN_TIMEOUT_SECONDS = 0.2
        controller.start()
        started = time.monotonic()
        with self.assertLogs("services.controller", level="WARNING"):
            controller.shutdown()
        elapsed = time.monotonic() - started
        self.assertTrue(vision.entered.is_set())
        self.assertLess(elapsed, 0.6)
        vision.release.set()

    def test_finite_provider_close_completes_within_shutdown_deadline(self) -> None:
        class DelayedStopEndpoint(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.completed = threading.Event()

            def stop(self) -> None:
                self.stops += 1
                time.sleep(0.1)
                self.completed.set()

        vision = DelayedStopEndpoint()
        controller, _router = build_controller(vision=vision)
        controller.SHUTDOWN_JOIN_TIMEOUT_SECONDS = 0.5
        controller.start()
        started = time.monotonic()
        controller.shutdown()
        elapsed = time.monotonic() - started
        self.assertTrue(vision.completed.is_set())
        self.assertGreaterEqual(elapsed, 0.08)
        self.assertLess(elapsed, 0.5)

    def test_reset_leaves_endpoint_offline_when_close_does_not_finish(self) -> None:
        class BlockingStopEndpoint(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.entered = threading.Event()
                self.release = threading.Event()

            def stop(self) -> None:
                self.stops += 1
                self.entered.set()
                self.release.wait()

        gantry = BlockingStopEndpoint()
        hydro = Endpoint()
        controller, _router = build_controller(gantry=gantry, hydro=hydro)
        controller.RESET_BARRIER_TIMEOUT_SECONDS = 0.2
        controller.start()
        started = time.monotonic()
        controller.reset_serial()
        reset_done = threading.Event()
        controller.submit("reset marker", reset_done.set, lane="reset")
        self.assertTrue(reset_done.wait(timeout=1.0))
        elapsed = time.monotonic() - started
        self.assertTrue(gantry.entered.is_set())
        self.assertLess(elapsed, 0.6)
        self.assertEqual(gantry.starts, 1)
        self.assertEqual(hydro.starts, 2)
        reset_events = controller.ui_events.drain()
        self.assertTrue(
            any(
                event.kind is EventKind.CONNECTION
                and event.source == "gantry"
                and not event.data.get("online")
                for event in reset_events
            )
        )
        gantry.release.set()
        controller.shutdown()

    def test_shutdown_cannot_be_overtaken_by_reset_reopen(self) -> None:
        class BlockingReopenEndpoint(Endpoint):
            def __init__(self) -> None:
                super().__init__()
                self.reopen_entered = threading.Event()
                self.release_reopen = threading.Event()
                self.running = False

            def start(self) -> None:
                self.starts += 1
                if self.starts == 2:
                    self.reopen_entered.set()
                    self.release_reopen.wait(timeout=1.0)
                self.running = True

            def stop(self) -> None:
                self.stops += 1
                self.running = False

        gantry = BlockingReopenEndpoint()
        controller, _router = build_controller(gantry=gantry)
        controller.SHUTDOWN_JOIN_TIMEOUT_SECONDS = 1.0
        controller.start()
        controller.reset_serial()
        self.assertTrue(gantry.reopen_entered.wait(timeout=1.0))

        shutdown_thread = threading.Thread(target=controller.shutdown)
        shutdown_thread.start()
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and not controller._shutdown_started:
            time.sleep(0.005)
        self.assertTrue(controller._shutdown_started)
        time.sleep(0.05)
        # The shutdown close must wait outside the per-Gantry lifecycle lock
        # until the in-progress reset reopen returns.
        self.assertEqual(gantry.stops, 1)
        gantry.release_reopen.set()
        shutdown_thread.join(timeout=1.5)
        self.assertFalse(shutdown_thread.is_alive())
        self.assertGreaterEqual(gantry.stops, 2)
        self.assertFalse(gantry.running)


if __name__ == "__main__":
    unittest.main()
