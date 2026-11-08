from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import AppConfig
from services.events import EventKind
from services.state import ApplicationState
from services.workflows import WorkflowService
from utils.errors import HardwareUnavailableError


class Endpoint:
    def __init__(self) -> None:
        self.groups: list[int] = []

    def send(self, _command: str) -> None:
        pass

    def run_group(self, group_id: int, _repeat_count: int = 1) -> None:
        self.groups.append(group_id)


class UnavailableArm(Endpoint):
    def run_group(self, _group_id: int, _repeat_count: int = 1) -> None:
        raise HardwareUnavailableError("/dev/ttyAMA1 is closed")


class UnavailableHydro(Endpoint):
    def send(self, _command: str) -> None:
        raise HardwareUnavailableError("/dev/arduino_hydroponic is closed")


class WorkflowFailureCompatibilityTests(unittest.TestCase):
    def test_unavailable_arm_warns_skips_group_and_allows_legacy_sequence(self) -> None:
        events = []
        workflow = WorkflowService(
            AppConfig(),
            ApplicationState(),
            Endpoint(),
            Endpoint(),
            UnavailableArm(),
            events.append,
            sleep=lambda _seconds: None,
        )

        completed = workflow.run_arm_group_interruptibly(6, lambda: False)

        self.assertTrue(completed)
        warnings = [event for event in events if event.kind is EventKind.OPERATOR_NOTICE]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].data["level"], "warning")
        self.assertIn("command 6 was skipped", str(warnings[0].data["message"]))

    def test_unavailable_hydro_stops_pesticide_before_arm_action(self) -> None:
        arm = Endpoint()
        workflow = WorkflowService(
            AppConfig(),
            ApplicationState(),
            Endpoint(),
            UnavailableHydro(),
            arm,
            lambda _event: None,
            sleep=lambda _seconds: None,
        )

        with self.assertRaises(HardwareUnavailableError):
            workflow.pesticide()

        self.assertEqual(arm.groups, [])


if __name__ == "__main__":
    unittest.main()
