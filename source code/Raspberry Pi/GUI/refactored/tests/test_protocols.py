from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comm.protocols import (
    arm_group_run_frame,
    arm_group_stop_frame,
    gantry_grid_command,
    gantry_home_command,
    gantry_command_changes_position,
    gantry_relative_command,
    hydro_dose_command,
    hydro_dose_time_command,
    hydro_light_command,
    hydro_light_hour_command,
    hydro_target_ec_command,
    hydro_target_ph_command,
    hydro_water_command,
    line_command,
    parse_gantry_report,
    parse_hydro_status,
    validate_auto_dose_ml,
    validate_manual_dose_ml,
)
from utils.errors import ProtocolError


class ProtocolTests(unittest.TestCase):
    def test_gantry_command_generation(self) -> None:
        self.assertEqual(gantry_home_command(), "0 0")
        self.assertEqual(gantry_grid_command(6, 4), "6 4")
        self.assertEqual(gantry_relative_command("l"), "L")
        self.assertEqual(line_command("1 2"), b"1 2\n")
        with self.assertRaises(ProtocolError):
            gantry_grid_command(0, 1)
        with self.assertRaises(ProtocolError):
            line_command("bad\ncommand")
        for command in ("0 0", "1 1", "6 4", "U", "D", "L", "R", "G", "P", "O"):
            with self.subTest(command=command):
                self.assertTrue(gantry_command_changes_position(command))
        self.assertFalse(gantry_command_changes_position("X"))

    def test_hydroponics_command_generation(self) -> None:
        self.assertEqual(hydro_water_command(True), "WATER_PUMP:ON")
        self.assertEqual(hydro_light_command(False), "LIGHT:OFF")
        self.assertEqual(hydro_dose_command("acid", 5), "DOSE:ACID:5")
        self.assertEqual(hydro_dose_command("fert", 10), "DOSE:FERT:10")
        self.assertEqual(hydro_dose_command("pest", 11), "DOSE:PEST:11")
        self.assertEqual(hydro_target_ec_command(1500), "TARGET_EC:1500.0")
        self.assertEqual(hydro_target_ph_command(6.5), "TARGET_PH:6.50")
        self.assertEqual(hydro_light_hour_command(7, 19), ("LIGHT_ON_HOUR:7", "LIGHT_OFF_HOUR:19"))
        self.assertEqual(hydro_dose_time_command(5), "DOSE_TIME:5")
        with self.assertRaises(ProtocolError):
            hydro_light_hour_command(24, 19)
        with self.assertRaises(ProtocolError):
            hydro_dose_time_command(-1)
        self.assertEqual(hydro_dose_command("PEST", 11), "DOSE:PEST:11")

    def test_gui_reachable_numeric_validation(self) -> None:
        for invalid in (-100.0, float("nan"), float("inf"), float("-inf"), 50.0):
            with self.subTest(kind="ec", value=invalid), self.assertRaises(ProtocolError):
                hydro_target_ec_command(invalid)
        for invalid in (-0.5, float("nan"), float("inf"), float("-inf"), 6.25):
            with self.subTest(kind="ph", value=invalid), self.assertRaises(ProtocolError):
                hydro_target_ph_command(invalid)
        for invalid in (-5, 3, 7):
            with self.subTest(kind="auto", value=invalid), self.assertRaises(ProtocolError):
                validate_auto_dose_ml(invalid)
        for invalid in (0, 4, 6, 11):
            with self.subTest(kind="manual", value=invalid), self.assertRaises(ProtocolError):
                validate_manual_dose_ml(invalid)
        self.assertEqual(validate_auto_dose_ml(0), 0)
        self.assertEqual(validate_auto_dose_ml(10), 10)
        self.assertEqual(validate_manual_dose_ml(5), 5)
        self.assertEqual(validate_manual_dose_ml(15), 15)

    def test_arm_frames_match_legacy_servocontrol(self) -> None:
        self.assertEqual(arm_group_run_frame(6, 1), b"\x55\x55\x05\x06\x06\x01\x00")
        self.assertEqual(arm_group_stop_frame(), b"\x55\x55\x02\x07")

    def test_gantry_response_parsing(self) -> None:
        self.assertEqual(parse_gantry_report("START 3 2").kind, "start")
        report = parse_gantry_report("POS 3 2")
        self.assertEqual((report.kind, report.x, report.y), ("pos", 3, 2))
        self.assertEqual(parse_gantry_report("POS x 2").kind, "malformed")
        self.assertEqual(parse_gantry_report("Homing complete.").kind, "home_complete")
        self.assertEqual(parse_gantry_report("Motors disabled.").kind, "disabled")

    def test_hydro_status_requires_complete_numeric_record_and_binary_bits(self) -> None:
        status = parse_hydro_status("STAT,1234,75.5,1400.0,6.25,1,0,1,0,1")
        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.milliseconds, 1234)
        self.assertTrue(status.light_on)
        self.assertTrue(status.pesticide_on)
        extended = parse_hydro_status(
            "STAT,1234,75.5,1400.0,6.25,1,0,1,0,1,legacy-extension"
        )
        self.assertIsNotNone(extended)
        assert extended is not None
        self.assertEqual(extended.milliseconds, 1234)
        for malformed in (
            "STAT,1234,75.5",
            "STAT,clock,75.5,1400.0,6.25,1,0,1,0,1",
            "STAT,1234,75.5,1400.0,6.25,2,0,1,0,1",
            "STAT,1234,75.5,1400.0,6.25,true,0,1,0,1",
            "NOPE,1234,75.5,1400.0,6.25,1,0,1,0,1",
        ):
            with self.subTest(malformed=malformed):
                self.assertIsNone(parse_hydro_status(malformed))


if __name__ == "__main__":
    unittest.main()
