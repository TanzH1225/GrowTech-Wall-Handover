from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_controller
from config.settings import AppConfig
from services.controller import ApplicationController
from services.events import AppEvent, EventKind, UiEventQueue
from services.state import ApplicationEventRouter, ApplicationState


class EventRoutingTests(unittest.TestCase):
    def test_explicit_start_preserves_legacy_provider_order(self) -> None:
        calls: list[str] = []

        class Endpoint:
            def __init__(self, name: str) -> None:
                self.name = name

            def start(self) -> None:
                calls.append(self.name)

            def stop(self) -> None:
                pass

            def send(self, _command: str) -> None:
                pass

            def run_group(self, _group_id: int, _repeat_count: int = 1) -> None:
                pass

            def stop_group(self) -> None:
                pass

            def capture(self, _plant: int):
                raise AssertionError("capture not expected")

        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        controller = ApplicationController(
            AppConfig(),
            state,
            events,
            router,
            Endpoint("gantry"),
            Endpoint("hydroponics"),
            Endpoint("arm"),
            Endpoint("vision"),
            simulation=True,
        )
        controller.start()
        controller.shutdown()
        self.assertEqual(calls, ["vision", "arm", "gantry", "hydroponics"])

    def test_worker_event_is_handled_only_when_main_thread_drains(self) -> None:
        events = UiEventQueue()
        producer_thread_ids: list[int] = []

        def producer() -> None:
            producer_thread_ids.append(threading.get_ident())
            events.publish(AppEvent(EventKind.LOG, "worker", {"message": "done"}))

        worker = threading.Thread(target=producer)
        worker.start()
        worker.join()
        handler_thread_id = threading.get_ident()
        drained = events.drain()
        self.assertNotEqual(producer_thread_ids[0], handler_thread_id)
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0].data["message"], "done")

    def test_router_keeps_ui_queue_order_atomic_with_state_order(self) -> None:
        class BlockingPositionQueue(UiEventQueue):
            def __init__(self) -> None:
                super().__init__()
                self.position_enqueue_entered = threading.Event()
                self.release_position = threading.Event()

            def publish(self, event: AppEvent) -> None:
                if event.kind is EventKind.GANTRY_POSITION:
                    self.position_enqueue_entered.set()
                    self.release_position.wait(timeout=1.0)
                super().publish(event)

        state = ApplicationState()
        events = BlockingPositionQueue()
        router = ApplicationEventRouter(state, events)
        router.publish(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "1 1", "x": 1, "y": 1},
            )
        )
        events.drain()

        position_thread = threading.Thread(
            target=lambda: router.publish(
                AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1})
            )
        )
        request_thread = threading.Thread(
            target=lambda: router.publish(
                AppEvent(
                    EventKind.GANTRY_REQUEST,
                    "gantry",
                    {"command": "2 1", "x": 2, "y": 1},
                )
            )
        )
        position_thread.start()
        self.assertTrue(events.position_enqueue_entered.wait(timeout=1.0))
        request_thread.start()
        time.sleep(0.05)
        try:
            self.assertTrue(request_thread.is_alive())
            self.assertIsNone(state.snapshot().requested_command)
        finally:
            events.release_position.set()
            position_thread.join(timeout=1.0)
            request_thread.join(timeout=1.0)

        self.assertFalse(position_thread.is_alive())
        self.assertFalse(request_thread.is_alive())
        routed = events.drain()
        self.assertEqual(
            [event.kind for event in routed],
            [EventKind.GANTRY_POSITION, EventKind.GANTRY_REQUEST],
        )
        snapshot = state.snapshot()
        self.assertFalse(snapshot.position_valid)
        self.assertEqual(snapshot.requested_command, "2 1")

    def test_gui_facade_schedules_controller_work_and_returns_events(self) -> None:
        controller = create_controller(AppConfig(), simulate=True)
        controller.start()
        controller.ui_events.drain()
        controller.move_to(2, 3)
        deadline = time.monotonic() + 1
        received = []
        while time.monotonic() < deadline:
            received.extend(controller.ui_events.drain())
            if any(event.kind is EventKind.GANTRY_POSITION for event in received):
                break
            time.sleep(0.01)
        controller.shutdown()
        self.assertTrue(any(event.kind is EventKind.GANTRY_POSITION for event in received))
        self.assertEqual(
            (controller.state.snapshot().current_x, controller.state.snapshot().current_y),
            (2, 3),
        )


if __name__ == "__main__":
    unittest.main()
