from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui.main_window import (
    ACTION_COLOR,
    DISABLED_COLOR,
    GRID_BORDER_WIDTH,
    GRID_SELECTED_BORDER_COLOR,
    GRID_UNSELECTED_COLOR,
    MOVEMENT_COLOR,
    MOVING_COLOR,
    REACHED_COLOR,
    GrowTechWindow,
    messagebox,
)
from domain.models import HydroStatus
from services.events import AppEvent, EventKind


class FakeButton:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class FakePopup:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class FakeRoot:
    def __init__(self) -> None:
        self.callbacks: dict[str, object] = {}

    def after(self, _milliseconds: int, callback: object) -> str:
        identifier = f"after-{len(self.callbacks) + 1}"
        self.callbacks[identifier] = callback
        return identifier

    def after_cancel(self, identifier: str) -> None:
        self.callbacks.pop(identifier, None)


class FakeVariable:
    def __init__(self) -> None:
        self.value: object = None

    def set(self, value: object) -> None:
        self.value = value


class GuiCompatibilityTests(unittest.TestCase):
    def test_dose_status_lights_a_b_and_acid_without_breaking_water_light(self) -> None:
        window = GrowTechWindow.__new__(GrowTechWindow)
        window._water = FakeVariable()
        window._ec = FakeVariable()
        window._ph = FakeVariable()
        window._water_button = FakeButton()
        window._light_button = FakeButton()
        window._hydro_indicators = {
            name: FakeButton() for name in ("A", "B", "Acid", "Water", "Light")
        }

        fertilizer = HydroStatus(1000, 72.5, 1450.0, 6.5, True, True, False, True, False)
        window._update_hydro(fertilizer)
        self.assertEqual(window._hydro_indicators["A"].options["bg"], ACTION_COLOR)
        self.assertEqual(window._hydro_indicators["B"].options["bg"], ACTION_COLOR)
        self.assertEqual(window._hydro_indicators["Acid"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["Water"].options["bg"], MOVEMENT_COLOR)
        self.assertEqual(window._hydro_indicators["Light"].options["bg"], MOVING_COLOR)

        acid = HydroStatus(2000, 72.5, 1450.0, 6.5, True, True, True, False, False)
        window._update_hydro(acid)
        self.assertEqual(window._hydro_indicators["A"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["B"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["Acid"].options["bg"], ACTION_COLOR)

        finished = HydroStatus(3000, 72.5, 1450.0, 6.5, True, True, False, False, False)
        window._update_hydro(finished)
        self.assertEqual(window._hydro_indicators["A"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["B"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["Acid"].options["bg"], DISABLED_COLOR)
        self.assertEqual(window._hydro_indicators["Water"].options["bg"], MOVEMENT_COLOR)
        self.assertEqual(window._hydro_indicators["Light"].options["bg"], MOVING_COLOR)

    def test_initial_grid_button_uses_legacy_green_unselected_style(self) -> None:
        class Controller:
            def move_to(self, _x: int, _y: int) -> None:
                pass

        window = GrowTechWindow.__new__(GrowTechWindow)
        window._controller = Controller()
        created = FakeButton()

        with patch("gui.main_window.tk.Button", return_value=created) as button:
            result = window._create_grid_position_button(object(), 1, 1, 1)

        self.assertIs(result, created)
        options = button.call_args.kwargs
        self.assertEqual(GRID_UNSELECTED_COLOR, REACHED_COLOR)
        self.assertEqual(options["bg"], REACHED_COLOR)
        self.assertEqual(options["bd"], 1)
        self.assertEqual(options["relief"], "raised")
        self.assertEqual(options["highlightthickness"], GRID_BORDER_WIDTH)
        self.assertEqual(options["highlightbackground"], REACHED_COLOR)
        self.assertEqual(options["highlightcolor"], REACHED_COLOR)
        self.assertFalse(options["takefocus"])

    def test_selected_grid_button_uses_border_without_whitening_previous(self) -> None:
        window = GrowTechWindow.__new__(GrowTechWindow)
        previous = FakeButton()
        selected = FakeButton()
        previous_vision = FakeButton()
        selected_vision = FakeButton()
        window._grid_buttons = {(1, 1): previous, (2, 1): selected}
        window._vision_buttons = {
            (1, 1): previous_vision,
            (2, 1): selected_vision,
        }
        window._current_position = (1, 1)
        window._gantry_state = FakeVariable()

        window._mark_position(2, 1, moving=True)
        for button in (previous, previous_vision):
            self.assertEqual(button.options["bg"], REACHED_COLOR)
            self.assertEqual(button.options["bd"], 1)
            self.assertEqual(button.options["relief"], "raised")
            self.assertEqual(button.options["highlightbackground"], REACHED_COLOR)
            self.assertEqual(button.options["highlightcolor"], REACHED_COLOR)
        for button in (selected, selected_vision):
            self.assertNotEqual(button.options["bg"], REACHED_COLOR)
            self.assertEqual(button.options["bd"], 1)
            self.assertEqual(button.options["relief"], "raised")
            self.assertEqual(
                button.options["highlightbackground"], GRID_SELECTED_BORDER_COLOR
            )
            self.assertEqual(
                button.options["highlightcolor"], GRID_SELECTED_BORDER_COLOR
            )

        window._mark_position(2, 1, moving=False)
        for button in (selected, selected_vision):
            self.assertEqual(button.options["bg"], REACHED_COLOR)
            self.assertEqual(button.options["bd"], 1)
            self.assertEqual(button.options["relief"], "raised")
            self.assertEqual(
                button.options["highlightbackground"], GRID_SELECTED_BORDER_COLOR
            )

    def test_dedicated_scan_only_and_full_auto_actions_route_exact_modes(self) -> None:
        class Controller:
            def __init__(self) -> None:
                self.modes: list[str] = []

            def start_automation(self, mode: str) -> None:
                self.modes.append(mode)

        window = GrowTechWindow.__new__(GrowTechWindow)
        window._controller = Controller()
        scan_popup = FakePopup()
        full_popup = FakePopup()

        window._start_automation("scan", scan_popup)
        window._start_automation("full", full_popup)

        self.assertEqual(window._controller.modes, ["scan", "full"])
        self.assertTrue(scan_popup.destroyed)
        self.assertTrue(full_popup.destroyed)

    def test_exclusive_workflow_visibly_disables_manual_and_auto_controls(self) -> None:
        window = GrowTechWindow.__new__(GrowTechWindow)
        manual = FakeButton()
        auto = FakeButton()
        window._manual_buttons = [manual, auto]
        window._auto_button = auto
        window._automation_active = False
        window._exclusive_operation_active = True

        window._refresh_control_state()
        self.assertEqual(manual.options["state"], "disabled")
        self.assertEqual(auto.options["state"], "disabled")

        window._exclusive_operation_active = False
        window._refresh_control_state()
        self.assertEqual(manual.options["state"], "normal")
        self.assertEqual(auto.options["state"], "normal")

    def test_simulation_keeps_fast_exclusive_workflow_lock_visible(self) -> None:
        class Controller:
            simulation = True

        window = GrowTechWindow.__new__(GrowTechWindow)
        window._main_thread_id = threading.get_ident()
        window._controller = Controller()
        window.root = FakeRoot()
        window._log_message = lambda _message: None
        manual = FakeButton()
        auto = FakeButton()
        window._manual_buttons = [manual, auto]
        window._auto_button = auto
        window._automation_active = False
        window._exclusive_operation_active = False
        window._operation_release_after_id = None

        window._handle_event(
            AppEvent(
                EventKind.OPERATION_STATE,
                "pesticide",
                {"operation": "Pesticide", "running": True},
            )
        )
        window._handle_event(
            AppEvent(
                EventKind.OPERATION_STATE,
                "pesticide",
                {
                    "operation": "Pesticide",
                    "running": False,
                    "outcome": "complete",
                },
            )
        )

        self.assertEqual(manual.options["state"], "disabled")
        self.assertEqual(auto.options["state"], "disabled")
        self.assertEqual(len(window.root.callbacks), 1)
        callback = next(iter(window.root.callbacks.values()))
        callback()
        self.assertEqual(manual.options["state"], "normal")
        self.assertEqual(auto.options["state"], "normal")

    def test_hardware_mode_releases_fast_exclusive_workflow_without_delay(self) -> None:
        class Controller:
            simulation = False

        window = GrowTechWindow.__new__(GrowTechWindow)
        window._main_thread_id = threading.get_ident()
        window._controller = Controller()
        window.root = FakeRoot()
        window._log_message = lambda _message: None
        manual = FakeButton()
        auto = FakeButton()
        window._manual_buttons = [manual, auto]
        window._auto_button = auto
        window._automation_active = False
        window._exclusive_operation_active = False
        window._operation_release_after_id = None

        window._handle_event(
            AppEvent(
                EventKind.OPERATION_STATE,
                "pesticide",
                {"operation": "Pesticide", "running": True},
            )
        )
        window._handle_event(
            AppEvent(
                EventKind.OPERATION_STATE,
                "pesticide",
                {
                    "operation": "Pesticide",
                    "running": False,
                    "outcome": "complete",
                },
            )
        )

        self.assertEqual(manual.options["state"], "normal")
        self.assertEqual(auto.options["state"], "normal")
        self.assertEqual(window.root.callbacks, {})

    def test_endpoint_error_event_uses_visible_operator_dialog(self) -> None:
        window = GrowTechWindow.__new__(GrowTechWindow)
        window._main_thread_id = threading.get_ident()
        window.root = object()
        logged: list[str] = []
        window._log_message = logged.append

        with patch.object(messagebox, "showerror") as showerror:
            window._handle_event(
                AppEvent(
                    EventKind.ERROR,
                    "hydroponics",
                    {"message": "Serial endpoint is closed"},
                )
            )

        showerror.assert_called_once_with(
            "Hydroponics", "Serial endpoint is closed", parent=window.root
        )
        self.assertEqual(logged, ["hydroponics: Serial endpoint is closed"])

    def test_legacy_arm_skip_notice_uses_visible_warning_dialog(self) -> None:
        window = GrowTechWindow.__new__(GrowTechWindow)
        window._main_thread_id = threading.get_ident()
        window.root = object()
        window._log_message = lambda _message: None
        notice = AppEvent(
            EventKind.OPERATOR_NOTICE,
            "arm",
            {
                "level": "warning",
                "title": "ServoControl",
                "message": "Robotic arm command 5 was skipped",
            },
        )

        with patch.object(messagebox, "showwarning") as showwarning:
            window._handle_event(notice)

        showwarning.assert_called_once_with(
            "ServoControl",
            "Robotic arm command 5 was skipped",
            parent=window.root,
        )


if __name__ == "__main__":
    unittest.main()
