from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.events import AppEvent, EventKind, UiEventQueue
from services.state import ApplicationEventRouter, ApplicationState


class GantryPositionValidityTests(unittest.TestCase):
    def test_home_complete_releases_wait_without_a_pos_report(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        result: list[bool] = []
        before_home = state.snapshot().home_generation
        waiter = threading.Thread(
            target=lambda: result.append(
                state.wait_for_home(before_home, lambda: False)
            )
        )
        waiter.start()
        router.publish(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
        waiter.join(timeout=1.0)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(result, [True])
        self.assertFalse(
            any(event.kind is EventKind.GANTRY_POSITION for event in events.drain())
        )

    def test_expected_legacy_home_position_can_also_complete_home_wait(self) -> None:
        state = ApplicationState()
        before = state.snapshot()
        state.apply(AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "0 0"}))
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))

        self.assertTrue(
            state.wait_for_home(
                before.home_generation,
                lambda: False,
                after_position_generation=before.position_generation,
                expected_position=(1, 1),
            )
        )

    def test_only_fresh_in_range_pos_makes_position_valid(self) -> None:
        state = ApplicationState()
        initial = state.snapshot()
        self.assertFalse(initial.position_valid)
        self.assertIsNone(initial.current_x)

        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 3, "y": 2}))
        confirmed = state.snapshot()
        self.assertTrue(confirmed.position_valid)
        self.assertEqual((confirmed.current_x, confirmed.current_y), (3, 2))

        state.apply(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "4 2", "x": 4, "y": 2},
            )
        )
        requested = state.snapshot()
        self.assertFalse(requested.position_valid)
        self.assertEqual(requested.requested_command, "4 2")
        self.assertEqual((requested.requested_x, requested.requested_y), (4, 2))

        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 9, "y": 2}))
        self.assertFalse(state.snapshot().position_valid)
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 4, "y": 2}))
        self.assertTrue(state.snapshot().position_valid)

    def test_mismatched_pos_does_not_confirm_newer_requested_target(self) -> None:
        state = ApplicationState()
        state.apply(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "1 1", "x": 1, "y": 1},
            )
        )
        state.apply(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "2 1", "x": 2, "y": 1},
            )
        )
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        mismatch = state.snapshot()
        self.assertFalse(mismatch.position_valid)
        self.assertEqual((mismatch.requested_x, mismatch.requested_y), (2, 1))
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 1}))
        matched = state.snapshot()
        self.assertTrue(matched.position_valid)
        self.assertEqual((matched.current_x, matched.current_y), (2, 1))
        self.assertIsNone(matched.requested_command)

    def test_next_accepts_fresh_pos_with_or_without_start(self) -> None:
        state = ApplicationState()
        state.apply(AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "G"}))
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        self.assertTrue(state.snapshot().position_valid)
        state.apply(AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "G"}))
        state.apply(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 1, "y": 1}))
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        self.assertTrue(state.snapshot().position_valid)

    def test_explicit_target_rejects_stale_start_and_router_marks_reports(self) -> None:
        state = ApplicationState()
        events = UiEventQueue()
        router = ApplicationEventRouter(state, events)
        router.publish(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "2 1", "x": 2, "y": 1},
            )
        )
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 1, "y": 1}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        rejected = events.drain()
        self.assertFalse(state.snapshot().position_valid)
        motion = [
            event
            for event in rejected
            if event.kind in (EventKind.GANTRY_START, EventKind.GANTRY_POSITION)
        ]
        self.assertEqual([event.data["accepted"] for event in motion], [False, False])
        self.assertEqual(
            (state.snapshot().requested_x, state.snapshot().requested_y), (2, 1)
        )
        router.publish(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 2, "y": 1}))
        router.publish(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 2, "y": 1}))
        accepted = [
            event
            for event in events.drain()
            if event.kind in (EventKind.GANTRY_START, EventKind.GANTRY_POSITION)
        ]
        self.assertEqual([event.data["accepted"] for event in accepted], [True, True])
        self.assertTrue(state.snapshot().position_valid)

    def test_serial_reset_blocks_delayed_reports_until_explicit_command(self) -> None:
        state = ApplicationState()
        state.apply(
            AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "serial reset"})
        )
        state.apply(AppEvent(EventKind.CONNECTION, "gantry", {"online": False}))
        state.apply(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
        self.assertFalse(
            state.apply(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 1, "y": 1}))
        )
        self.assertFalse(
            state.apply(
                AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1})
            )
        )
        self.assertFalse(state.snapshot().position_valid)
        state.apply(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "1 1", "x": 1, "y": 1},
            )
        )
        state.apply(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 1, "y": 1}))
        state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1}))
        self.assertTrue(state.snapshot().position_valid)

    def test_start_home_disable_timeout_and_disconnect_invalidate(self) -> None:
        invalidators = (
            AppEvent(EventKind.GANTRY_START, "gantry", {"x": 2, "y": 1}),
            AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"),
            AppEvent(EventKind.GANTRY_DISABLED, "gantry"),
            AppEvent(EventKind.GANTRY_TIMEOUT, "gantry"),
            AppEvent(EventKind.CONNECTION, "gantry", {"online": False}),
        )
        for invalidator in invalidators:
            with self.subTest(kind=invalidator.kind):
                state = ApplicationState()
                state.apply(
                    AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1})
                )
                self.assertTrue(state.snapshot().position_valid)
                state.apply(invalidator)
                self.assertFalse(state.snapshot().position_valid)

    def test_terminal_gantry_state_blocks_delayed_unsolicited_pos(self) -> None:
        blockers = (
            AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"),
            AppEvent(EventKind.GANTRY_DISABLED, "gantry"),
            AppEvent(EventKind.GANTRY_TIMEOUT, "gantry"),
            AppEvent(EventKind.CONNECTION, "gantry", {"online": False}),
        )
        for blocker in blockers:
            with self.subTest(kind=blocker.kind):
                state = ApplicationState()
                state.apply(
                    AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1})
                )
                state.apply(blocker)
                accepted = state.apply(
                    AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 1, "y": 1})
                )
                self.assertFalse(accepted)
                self.assertFalse(state.snapshot().position_valid)

    def test_reenable_home_preserves_explicit_move_request(self) -> None:
        state = ApplicationState()
        state.apply(AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "O"}))
        state.apply(AppEvent(EventKind.GANTRY_DISABLED, "gantry"))
        state.apply(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "3 2", "x": 3, "y": 2},
            )
        )
        state.apply(AppEvent(EventKind.GANTRY_HOME_COMPLETE, "gantry"))
        pending = state.snapshot()
        self.assertEqual(pending.requested_command, "3 2")
        self.assertEqual((pending.requested_x, pending.requested_y), (3, 2))
        self.assertTrue(
            state.apply(AppEvent(EventKind.GANTRY_START, "gantry", {"x": 3, "y": 2}))
        )
        self.assertTrue(
            state.apply(AppEvent(EventKind.GANTRY_POSITION, "gantry", {"x": 3, "y": 2}))
        )
        snapshot = state.snapshot()
        self.assertTrue(snapshot.position_valid)
        self.assertEqual((snapshot.current_x, snapshot.current_y), (3, 2))


if __name__ == "__main__":
    unittest.main()
