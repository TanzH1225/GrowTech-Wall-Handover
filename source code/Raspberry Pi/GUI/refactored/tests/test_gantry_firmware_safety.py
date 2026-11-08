"""Static regression checks for physical Gantry homing safety boundaries."""

from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MOTION_SOURCE = (
    REPOSITORY_ROOT / "gantry_main_refactored" / "GantryMotion.cpp"
).read_text(encoding="utf-8")


class GantryFirmwareSafetyTests(unittest.TestCase):
    def test_homing_fault_disables_drivers_before_permanent_halt(self) -> None:
        match = re.search(
            r"void GantryMotion::errorStop\([^)]*\) \{(?P<body>.*?)\n\}",
            MOTION_SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("disableMotors();", body)
        self.assertLess(body.index("disableMotors();"), body.index("while (true)"))

    def test_x_homing_debounces_without_continuing_step_pulses(self) -> None:
        x_homing = MOTION_SOURCE.split(
            "void GantryMotion::bumpHomeX()", 1
        )[1].split("void GantryMotion::bumpHomeDualY()", 1)[0]

        self.assertGreaterEqual(x_homing.count("stepperX_.setSpeed(0);"), 4)
        self.assertEqual(
            x_homing.count("if (!confirmed) {\n      stepperX_.runSpeed();"),
            2,
        )
        self.assertNotIn(
            "    stepperX_.runSpeed();\n  }\n  stepperX_.stop();",
            x_homing,
        )


if __name__ == "__main__":
    unittest.main()
