from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import AppConfig
from domain.grid import SNAKE_SEQUENCE
from services.automation import AutomationService
from services.events import UiEventQueue
from services.state import ApplicationEventRouter, ApplicationState
from services.workflows import WorkflowService
from simulation.controllers import MockArmController, MockGantryController, MockHydroponicsController
from simulation.vision import MockVisionService


class AutomationStateTests(unittest.TestCase):
    def _run_full(self, labels: dict[int, str]):
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = MockGantryController(router.publish)
        hydro = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        vision = MockVisionService(labels)
        for service in (gantry, hydro, arm, vision):
            service.start()
        workflows = WorkflowService(
            AppConfig(),
            state,
            gantry,
            hydro,
            arm,
            router.publish,
            sleep=lambda _seconds: None,
        )
        delays: list[float] = []
        automation = AutomationService(
            state,
            gantry,
            vision,
            workflows,
            router.publish,
            post_capture_sleep=delays.append,
        )
        automation.start("full")
        self.assertTrue(automation.wait(timeout=2.0))
        return state, events, gantry, hydro, arm, vision, delays

    def test_scan_mode_visits_legacy_sequence_and_transitions(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = MockGantryController(router.publish)
        hydro = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        vision = MockVisionService()
        for service in (gantry, hydro, arm, vision):
            service.start()
        workflows = WorkflowService(
            AppConfig(), state, gantry, hydro, arm, router.publish, sleep=lambda _seconds: None
        )
        automation = AutomationService(
            state,
            gantry,
            vision,
            workflows,
            router.publish,
            post_capture_sleep=lambda _seconds: None,
        )
        automation.start("scan")
        self.assertTrue(automation.wait(timeout=2.0))
        self.assertEqual(gantry.commands[0], "0 0")
        self.assertEqual(len(gantry.commands), 25)
        self.assertEqual(vision.captures, SNAKE_SEQUENCE)
        history = state.automation_history()
        self.assertIn("homing", history)
        self.assertIn("moving", history)
        self.assertIn("capturing", history)
        self.assertEqual(history[-1], "complete")

    def test_full_mode_preserves_label_to_action_dispatch(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = MockGantryController(router.publish)
        hydro = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        labels = {plant: "No detection" for plant in SNAKE_SEQUENCE}
        vision = MockVisionService(labels)
        for service in (gantry, hydro, arm, vision):
            service.start()
        workflows = WorkflowService(
            AppConfig(), state, gantry, hydro, arm, router.publish, sleep=lambda _seconds: None
        )
        automation = AutomationService(
            state, gantry, vision, workflows, router.publish, post_capture_sleep=lambda _seconds: None
        )
        automation.start("full")
        self.assertTrue(automation.wait(timeout=2.0))
        self.assertEqual(arm.groups, tuple((5, 1) for _ in SNAKE_SEQUENCE))
        self.assertIn("acting", state.automation_history())

    def test_full_mode_matured_branch_runs_harvest_then_transplant(self) -> None:
        labels = {plant: "No detection" for plant in SNAKE_SEQUENCE}
        labels[1] = "Matured"
        _state, events, gantry, _hydro, arm, _vision, delays = self._run_full(labels)
        self.assertEqual(
            arm.groups[:6],
            ((1, 1), (2, 1), (5, 1), (3, 1), (4, 1), (5, 1)),
        )
        self.assertEqual(
            gantry.commands[:6],
            ("0 0", "1 1", "2 1", "1 1", "6 1", "1 1"),
        )
        vision_events = [
            event
            for event in events.drain(limit=1000)
            if event.kind.value == "vision.result"
        ]
        self.assertEqual(len(vision_events), 24)
        self.assertTrue(all(bool(event.data["auto_close"]) for event in vision_events))
        self.assertEqual(delays, [0.1] * 24)

    def test_full_mode_disease_branch_runs_pesticide_sequence(self) -> None:
        labels = {plant: "No detection" for plant in SNAKE_SEQUENCE}
        labels[1] = "Diseased"
        _state, _events, _gantry, hydro, arm, _vision, _delays = self._run_full(labels)
        self.assertEqual(hydro.commands[0], "DOSE:PEST:11")
        self.assertEqual(arm.groups[:2], ((6, 1), (5, 1)))

    def test_stop_during_final_capture_gap_finishes_stopped_not_complete(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = MockGantryController(router.publish)
        hydro = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        vision = MockVisionService()
        for service in (gantry, hydro, arm, vision):
            service.start()
        workflows = WorkflowService(
            AppConfig(), state, gantry, hydro, arm, router.publish, sleep=lambda _seconds: None
        )
        automation: AutomationService

        def stop_on_final_gap(_seconds: float) -> None:
            if len(vision.captures) == len(SNAKE_SEQUENCE):
                automation.request_stop()

        automation = AutomationService(
            state,
            gantry,
            vision,
            workflows,
            router.publish,
            post_capture_sleep=stop_on_final_gap,
        )
        automation.start("scan")
        self.assertTrue(automation.wait(timeout=2.0))
        history = state.automation_history()
        self.assertEqual(history[-1], "stopped")
        self.assertNotEqual(history[-1], "complete")

    def test_stop_interrupts_scan_gap_before_full_second_expires(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = MockGantryController(router.publish)
        hydro = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        vision = MockVisionService()
        for service in (gantry, hydro, arm, vision):
            service.start()
        workflows = WorkflowService(
            AppConfig(),
            state,
            gantry,
            hydro,
            arm,
            router.publish,
            sleep=lambda _seconds: None,
        )
        intervals: list[float] = []
        automation: AutomationService

        def stop_after_three_intervals(seconds: float) -> None:
            intervals.append(seconds)
            if len(intervals) == 3:
                automation.request_stop()

        automation = AutomationService(
            state,
            gantry,
            vision,
            workflows,
            router.publish,
            post_capture_sleep=stop_after_three_intervals,
        )
        automation.start("scan")
        self.assertTrue(automation.wait(timeout=2.0))

        self.assertEqual(intervals, [0.1, 0.1, 0.1])
        self.assertLess(sum(intervals), 1.0)
        self.assertEqual(vision.captures, (1,))
        self.assertEqual(state.automation_history()[-1], "stopped")

    def test_concurrent_start_cannot_clear_stop_request(self) -> None:
        class GatedLock:
            def __init__(self) -> None:
                self._lock = threading.Lock()
                self.entered = threading.Event()
                self.release = threading.Event()
                self._gate_first_entry = True

            def __enter__(self):
                self._lock.acquire()
                if self._gate_first_entry:
                    self._gate_first_entry = False
                    self.entered.set()
                    self.release.wait(timeout=1.0)
                return self

            def __exit__(self, _exc_type, _exc, _traceback) -> None:
                self._lock.release()

        class BlockingGantry:
            def __init__(self) -> None:
                self.send_entered = threading.Event()
                self.release_send = threading.Event()

            def send(self, _command: str) -> None:
                self.send_entered.set()
                self.release_send.wait(timeout=1.0)

        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        gantry = BlockingGantry()
        automation = AutomationService(
            state,
            gantry,
            object(),
            object(),
            router.publish,
            post_capture_sleep=lambda _seconds: None,
        )
        gate = GatedLock()
        automation._lock = gate

        starter = threading.Thread(target=lambda: automation.start("scan"))
        stopper = threading.Thread(target=automation.request_stop)
        starter.start()
        self.assertTrue(gate.entered.wait(timeout=1.0))
        stopper.start()
        gate.release.set()
        starter.join(timeout=1.0)
        stopper.join(timeout=1.0)
        self.assertFalse(starter.is_alive())
        self.assertFalse(stopper.is_alive())
        self.assertTrue(automation._stop.is_set())
        self.assertTrue(gantry.send_entered.wait(timeout=1.0))
        gantry.release_send.set()
        self.assertTrue(automation.wait(timeout=1.0))
        self.assertEqual(state.automation_history()[-1], "stopped")


if __name__ == "__main__":
    unittest.main()
