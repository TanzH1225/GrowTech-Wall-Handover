from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
from config.settings import AppConfig
from utils.errors import HardwareUnavailableError


class HardwarePlatformGateTests(unittest.TestCase):
    def test_verified_pi_evidence_is_accepted_without_opening_devices(self) -> None:
        app.verify_hardware_platform(
            system="Linux",
            machine="aarch64",
            model_text="Raspberry Pi 5 Model B Rev 1.0",
        )

    def test_unverified_hosts_are_directed_to_simulation(self) -> None:
        for evidence in (
            ("Windows", "AMD64", ""),
            ("Linux", "x86_64", "Raspberry Pi"),
            ("Linux", "aarch64", "Generic ARM board"),
        ):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(
                HardwareUnavailableError, "--simulate"
            ):
                app.verify_hardware_platform(*evidence)

    def test_hardware_factory_checks_platform_before_hardware_imports(self) -> None:
        with patch.object(
            app,
            "verify_hardware_platform",
            side_effect=HardwareUnavailableError("fixture: use --simulate"),
        ), patch.dict(sys.modules, {"serial": None, "cv2": None, "ultralytics": None}):
            with self.assertRaisesRegex(HardwareUnavailableError, "--simulate"):
                app.create_controller(AppConfig(), simulate=False)

    def test_main_finally_shuts_down_after_window_construction_failure(self) -> None:
        class FakeController:
            def __init__(self) -> None:
                self.started = False
                self.shutdown_calls = 0

            def start(self) -> None:
                self.started = True

            def shutdown(self) -> None:
                self.shutdown_calls += 1

        fake_controller = FakeController()
        fake_gui = ModuleType("gui.main_window")

        class BrokenWindow:
            def __init__(self, _controller) -> None:
                raise RuntimeError("window fixture failure")

        fake_gui.GrowTechWindow = BrokenWindow
        with patch.object(app, "create_controller", return_value=fake_controller), patch.dict(
            sys.modules, {"gui.main_window": fake_gui}
        ):
            with self.assertRaisesRegex(RuntimeError, "window fixture failure"):
                app.main(["--simulate"])
        self.assertTrue(fake_controller.started)
        self.assertEqual(fake_controller.shutdown_calls, 1)


if __name__ == "__main__":
    unittest.main()
