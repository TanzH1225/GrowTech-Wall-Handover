from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.events import AppEvent, EventKind, UiEventQueue
from comm.clients import HydroponicsSerialClient
from domain.grid import SNAKE_SEQUENCE, position_for_plant
from services.state import ApplicationEventRouter, ApplicationState
from simulation.controllers import MockArmController, MockGantryController, MockHydroponicsController
from simulation.vision import MockVisionService


class ManualTimeoutScheduler:
    def __init__(self) -> None:
        self.pending: list[dict[str, object]] = []

    def __call__(self, seconds: float, callback):
        timeout = {"seconds": seconds, "callback": callback, "cancelled": False}
        self.pending.append(timeout)

        def cancel() -> None:
            timeout["cancelled"] = True

        return cancel

    def fire_next(self) -> None:
        timeout = self.pending.pop(0)
        if not timeout["cancelled"]:
            timeout["callback"]()


class SimulationControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = ApplicationState()
        self.events = UiEventQueue()
        self.router = ApplicationEventRouter(self.state, self.events)

    def test_mock_gantry_records_and_reports_grid_move(self) -> None:
        gantry = MockGantryController(self.router.publish)
        gantry.start()
        before = self.state.snapshot().position_generation
        self.router.publish(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "3 2", "x": 3, "y": 2},
            )
        )
        gantry.send("3 2")
        snapshot = self.state.snapshot()
        self.assertGreater(snapshot.position_generation, before)
        self.assertEqual((snapshot.current_x, snapshot.current_y), (3, 2))
        self.assertEqual(gantry.commands, ("3 2",))

    def test_mock_next_matches_firmware_snake_state_and_reports_start_pos(self) -> None:
        gantry = MockGantryController(self.router.publish)
        gantry.start()
        self.events.drain()
        for _ in range(25):
            self.router.publish(
                AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "G"})
            )
            gantry.send("G")
        events = self.events.drain(limit=500)
        positions = [
            (int(event.data["x"]), int(event.data["y"]))
            for event in events
            if event.kind is EventKind.GANTRY_POSITION
        ]
        expected = [
            (position_for_plant(plant).x, position_for_plant(plant).y)
            for plant in SNAKE_SEQUENCE
        ]
        self.assertEqual(positions[:24], expected)
        self.assertEqual(positions[24], (1, 1))
        self.assertEqual(
            sum(event.kind is EventKind.GANTRY_START for event in events),
            50,
        )

    def test_disable_then_next_rehomes_logical_state_before_first_cell(self) -> None:
        gantry = MockGantryController(self.router.publish)
        gantry.start()
        self.router.publish(
            AppEvent(
                EventKind.GANTRY_REQUEST,
                "gantry",
                {"command": "3 2", "x": 3, "y": 2},
            )
        )
        gantry.send("3 2")
        self.router.publish(
            AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "O"})
        )
        gantry.send("O")
        self.events.drain()
        self.router.publish(
            AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "G"})
        )
        gantry.send("G")
        events = self.events.drain()
        positions = [
            (int(event.data["x"]), int(event.data["y"]))
            for event in events
            if event.kind is EventKind.GANTRY_POSITION
        ]
        self.assertEqual(positions, [(1, 1)])
        position_events = [
            event for event in events if event.kind is EventKind.GANTRY_POSITION
        ]
        self.assertEqual([event.data["accepted"] for event in position_events], [True])
        snapshot = self.state.snapshot()
        self.assertTrue(snapshot.position_valid)
        self.assertEqual((snapshot.current_x, snapshot.current_y), (1, 1))
        self.assertTrue(
            any(event.kind is EventKind.GANTRY_HOME_COMPLETE for event in events)
        )

    def test_mock_hydroponics_updates_complete_status(self) -> None:
        hydro = MockHydroponicsController(self.router.publish)
        hydro.start()
        hydro.send("WATER_PUMP:ON")
        status = self.state.snapshot().hydro_status
        self.assertIsNotNone(status)
        assert status is not None
        self.assertTrue(status.water_pump_on)
        self.assertEqual(hydro.commands, ("WATER_PUMP:ON",))

    def test_manual_fertilizer_and_acid_dose_status_lifecycle(self) -> None:
        scheduler = ManualTimeoutScheduler()
        hydro = MockHydroponicsController(
            self.router.publish,
            schedule_timeout=scheduler,
        )
        hydro.start()
        hydro.send("WATER_PUMP:ON")
        hydro.send("LIGHT:ON")

        hydro.send("DOSE:FERT:5")
        fertilizer = self.state.snapshot().hydro_status
        assert fertilizer is not None
        self.assertTrue(fertilizer.fertilizer_on)
        self.assertFalse(fertilizer.acid_on)
        self.assertTrue(fertilizer.water_pump_on)
        self.assertTrue(fertilizer.light_on)
        self.assertEqual(scheduler.pending[0]["seconds"], 5.0)
        scheduler.fire_next()
        fertilizer_finished = self.state.snapshot().hydro_status
        assert fertilizer_finished is not None
        self.assertFalse(fertilizer_finished.fertilizer_on)
        self.assertTrue(fertilizer_finished.water_pump_on)
        self.assertTrue(fertilizer_finished.light_on)

        hydro.send("DOSE:ACID:10")
        acid = self.state.snapshot().hydro_status
        assert acid is not None
        self.assertTrue(acid.acid_on)
        self.assertFalse(acid.fertilizer_on)
        self.assertEqual(scheduler.pending[0]["seconds"], 10.0)
        scheduler.fire_next()
        acid_finished = self.state.snapshot().hydro_status
        assert acid_finished is not None
        self.assertFalse(acid_finished.acid_on)
        self.assertTrue(acid_finished.water_pump_on)
        self.assertTrue(acid_finished.light_on)

    def test_dose_visibility_timer_exists_only_on_simulation_double(self) -> None:
        scheduler = ManualTimeoutScheduler()
        hydro = MockHydroponicsController(
            self.router.publish,
            schedule_timeout=scheduler,
        )

        self.assertIs(hydro._schedule_timeout, scheduler)
        self.assertNotIn("_schedule_timeout", vars(HydroponicsSerialClient))

    def test_restart_restores_both_nanos_to_startup_state(self) -> None:
        gantry = MockGantryController(self.router.publish)
        hydro = MockHydroponicsController(self.router.publish)
        gantry.start()
        hydro.start()
        gantry.send("3 2")
        hydro.send("WATER_PUMP:ON")
        hydro.send("LIGHT:ON")
        gantry.stop()
        hydro.stop()
        gantry.start()
        hydro.start()
        self.router.publish(
            AppEvent(EventKind.GANTRY_REQUEST, "gantry", {"command": "G"})
        )
        gantry.send("G")
        snapshot = self.state.snapshot()
        self.assertEqual((snapshot.current_x, snapshot.current_y), (1, 1))
        assert snapshot.hydro_status is not None
        self.assertFalse(snapshot.hydro_status.water_pump_on)
        self.assertFalse(snapshot.hydro_status.light_on)

    def test_mock_arm_and_vision_are_deterministic(self) -> None:
        arm = MockArmController(self.router.publish)
        vision = MockVisionService({2: "Matured"})
        arm.start()
        vision.start()
        arm.run_group(1)
        result = vision.capture(2)
        self.assertEqual(arm.groups, ((1, 1),))
        self.assertEqual(result.label, "Matured")
        self.assertIsNone(result.image_path)


if __name__ == "__main__":
    unittest.main()
