"""Recognizable four-tab Tk GUI with main-thread-only widget access."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from comm.protocols import (
    gantry_home_command,
    gantry_relative_command,
    validate_manual_dose_ml,
)
from domain.grid import GRID_NUMBERS, plant_for_xy, position_for_plant
from domain.models import HydroStatus, VisionResult
from services.controller import ApplicationController
from services.automation import AutomationMode
from services.events import AppEvent, EventKind
from utils.errors import GrowTechError


MOVEMENT_COLOR = "#4A90E2"
ACTION_COLOR = "#D64541"
CAPTURE_COLOR = "#8E44AD"
DISABLED_COLOR = "#CCCCCC"
MOVING_COLOR = "#F5A623"
REACHED_COLOR = "#7ED321"
GRID_UNSELECTED_COLOR = REACHED_COLOR
GRID_SELECTED_BORDER_COLOR = "#000000"
GRID_BORDER_WIDTH = 2
SIMULATION_OPERATION_LOCK_MS = 400


class GrowTechWindow:
    """Tk widget owner and sole consumer of the UI-event queue."""

    def __init__(self, controller: ApplicationController) -> None:
        self._controller = controller
        self._main_thread_id = threading.get_ident()
        self.root = tk.Tk()
        self.root.title(
            "GROW TECH WALL Controller"
            + (" [SIMULATION]" if controller.simulation else "")
        )
        self.root.geometry("800x480")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._status_labels: dict[str, tk.Label] = {}
        self._grid_buttons: dict[tuple[int, int], tk.Button] = {}
        self._vision_buttons: dict[tuple[int, int], tk.Button] = {}
        self._vision_labels: dict[int, tk.Label] = {}
        self._manual_buttons: list[tk.Button] = []
        self._current_position: tuple[int, int] | None = None
        self._water_on = False
        self._light_on = False
        self._last_dose: dict[str, float] = {"ACID": 0.0, "FERT": 0.0}
        self._dose_lock_minutes = 30.0
        self._last_photo: tk.PhotoImage | None = None
        self._automation_active = False
        self._exclusive_operation_active = False
        self._operation_release_after_id: str | None = None

        self._build_style()
        self._build_variables()
        self._build_tabs()
        self.root.after(self._controller.config.gui_poll_interval_ms, self._drain_events)

    def run(self) -> None:
        """Enter Tk's event loop on the constructing thread."""

        self._assert_main_thread()
        self.root.mainloop()

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0", font=("Helvetica", 10))

    def _build_variables(self) -> None:
        self._water = tk.StringVar(value="0.0 %")
        self._ec = tk.StringVar(value="0.0")
        self._ph = tk.StringVar(value="0.00")
        self._last_detection = tk.StringVar(value="N/A")
        self._plant_position = tk.StringVar(value="–")
        self._gantry_state = tk.StringVar(value="Idle")
        self._gantry_raw = tk.StringVar(value="-")
        self._arm_state = tk.StringVar(value="Idle")
        self._hydro_sent = tk.StringVar(value="")
        self._hydro_received = tk.StringVar(value="")
        self._ec_target = tk.StringVar(value="1500.0")
        self._ph_target = tk.StringVar(value="6.50")
        self._dose_time = tk.StringVar(value="5")
        self._light_on_hour = tk.StringVar(value="7")
        self._light_off_hour = tk.StringVar(value="19")

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        dashboard = ttk.Frame(notebook)
        gantry = ttk.Frame(notebook)
        hydro = ttk.Frame(notebook)
        vision = ttk.Frame(notebook)
        notebook.add(dashboard, text="Dashboard")
        notebook.add(gantry, text="Gantry & Arm")
        notebook.add(hydro, text="Hydroponic")
        notebook.add(vision, text="Vision")
        self._build_dashboard(dashboard)
        self._build_gantry_tab(gantry)
        self._build_hydro_tab(hydro)
        self._build_vision_tab(vision)

    def _build_dashboard(self, tab: ttk.Frame) -> None:
        status = ttk.Frame(tab)
        status.pack(fill="x", padx=5, pady=5)
        names = (
            ("gantry", "XY Gantry"),
            ("arm", "Robotic Arm"),
            ("hydroponics", "Dosing Module"),
            ("light", "Grow Light"),
            ("vision", "Camera"),
        )
        for column, (key, title) in enumerate(names):
            status.columnconfigure(column, weight=1)
            label = tk.Label(status, text=f"{title}: Offline", bg="#e0a0a0", relief="solid")
            label.grid(row=0, column=column, sticky="ew", padx=2)
            self._status_labels[key] = label
        reset = tk.Button(
            status,
            text="Reset Devices",
            command=self._controller.reset_serial,
            bg="#FF8C00",
            fg="white",
        )
        reset.grid(row=0, column=5, sticky="ew", padx=2)
        self._manual_buttons.append(reset)

        middle = ttk.Frame(tab)
        middle.pack(fill="both", expand=True, padx=8)
        middle.columnconfigure(0, weight=1)
        middle.columnconfigure(1, weight=1)
        sensors = ttk.LabelFrame(middle, text="Sensors")
        sensors.grid(row=0, column=0, sticky="nsew", padx=4)
        for row, (label, variable) in enumerate(
            (("Water Level:", self._water), ("EC (µS/cm):", self._ec), ("pH:", self._ph))
        ):
            ttk.Label(sensors, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=5)
            ttk.Label(sensors, textvariable=variable).grid(row=row, column=1, sticky="w")
        image_box = ttk.LabelFrame(middle, text="Last Image")
        image_box.grid(row=0, column=1, sticky="nsew", padx=4)
        self._last_image = tk.Label(image_box, text="No captured image", anchor="center")
        self._last_image.pack(fill="both", expand=True)

        info = ttk.Frame(tab)
        info.pack(fill="x", padx=10, pady=4)
        ttk.Label(info, text="Last Detection:").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self._last_detection).grid(row=0, column=1, sticky="w")
        ttk.Label(info, text="Plant Position:").grid(row=1, column=0, sticky="w")
        ttk.Label(info, textvariable=self._plant_position).grid(row=1, column=1, sticky="w")

        log_frame = ttk.LabelFrame(tab, text="Log / Notifications")
        log_frame.pack(fill="x", padx=8, pady=4)
        self._log = tk.Text(log_frame, height=4, state="disabled")
        self._log.pack(fill="x")
        self._log_message(
            "Simulation mode: no physical interfaces will be accessed."
            if self._controller.simulation
            else "Hardware mode selected; endpoint availability is shown above."
        )

    def _build_gantry_tab(self, tab: ttk.Frame) -> None:
        controls = ttk.Frame(tab)
        controls.pack(fill="x", padx=8, pady=6)
        actions: tuple[tuple[str, Any, str], ...] = (
            ("Home", lambda: self._controller.send_gantry(gantry_home_command()), MOVEMENT_COLOR),
            ("Up", lambda: self._controller.send_gantry(gantry_relative_command("U")), MOVEMENT_COLOR),
            ("Next", lambda: self._controller.send_gantry("G"), MOVEMENT_COLOR),
            ("Harvest", self._controller.harvest, ACTION_COLOR),
            ("Pesticide", self._controller.pesticide, ACTION_COLOR),
            ("Auto", self._choose_auto_mode, "#e0e0e0"),
            ("Capture", self._controller.capture_current, CAPTURE_COLOR),
            ("Left", lambda: self._controller.send_gantry(gantry_relative_command("L")), MOVEMENT_COLOR),
            ("Down", lambda: self._controller.send_gantry(gantry_relative_command("D")), MOVEMENT_COLOR),
            ("Right", lambda: self._controller.send_gantry(gantry_relative_command("R")), MOVEMENT_COLOR),
            ("Transplant", self._controller.transplant, ACTION_COLOR),
            ("Disable", lambda: self._controller.send_gantry("O"), MOVEMENT_COLOR),
        )
        for index, (text, command, color) in enumerate(actions):
            row, column = divmod(index, 7)
            button = tk.Button(controls, text=text, command=command, bg=color, fg="white" if color != "#e0e0e0" else "black")
            button.grid(row=row, column=column, sticky="ew", padx=3, pady=3)
            controls.columnconfigure(column, weight=1)
            self._manual_buttons.append(button)
            if text == "Auto":
                self._auto_button = button

        grid = ttk.Frame(tab)
        grid.pack(fill="both", expand=True, padx=10, pady=4)
        for row, numbers in enumerate(GRID_NUMBERS):
            grid.rowconfigure(row, weight=1)
            for column, plant in enumerate(numbers):
                grid.columnconfigure(column, weight=1)
                position = position_for_plant(plant)
                button = self._create_grid_position_button(
                    grid, plant, position.x, position.y
                )
                button.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
                self._grid_buttons[(position.x, position.y)] = button
                self._manual_buttons.append(button)

        bottom = ttk.Frame(tab)
        bottom.pack(fill="x", padx=10, pady=4)
        ttk.Label(bottom, text="Gantry:").grid(row=0, column=0)
        ttk.Label(bottom, textvariable=self._gantry_state, relief="groove").grid(row=0, column=1, sticky="ew")
        ttk.Label(bottom, text="Arm:").grid(row=0, column=2)
        ttk.Label(bottom, textvariable=self._arm_state, relief="groove").grid(row=0, column=3, sticky="ew")
        ttk.Label(bottom, textvariable=self._gantry_raw).grid(row=1, column=0, columnspan=4, sticky="ew")
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(3, weight=1)

    def _create_grid_position_button(
        self,
        parent: ttk.Frame,
        plant: int,
        x: int,
        y: int,
    ) -> tk.Button:
        """Create one legacy-green unselected Gantry position button."""

        return tk.Button(
            parent,
            text=str(plant),
            bg=GRID_UNSELECTED_COLOR,
            bd=1,
            relief="raised",
            highlightthickness=GRID_BORDER_WIDTH,
            highlightbackground=GRID_UNSELECTED_COLOR,
            highlightcolor=GRID_UNSELECTED_COLOR,
            takefocus=False,
            command=lambda: self._controller.move_to(x, y),
        )

    # Hydro controls are not registered in _manual_buttons: their separate
    # controller lane stays available during an exclusive Gantry/arm workflow.
    def _build_hydro_tab(self, tab: ttk.Frame) -> None:
        indicators = ttk.Frame(tab)
        indicators.pack(fill="x", padx=10, pady=(6, 0))
        self._hydro_indicators: dict[str, tk.Label] = {}
        for column, name in enumerate(("A", "B", "Acid", "Water", "Light")):
            indicators.columnconfigure(column, weight=1)
            label = tk.Label(
                indicators,
                text=name,
                bg=DISABLED_COLOR,
                fg="white",
                relief="solid",
            )
            label.grid(row=0, column=column, sticky="ew", padx=2)
            self._hydro_indicators[name] = label

        readings = ttk.LabelFrame(tab, text="Sensor Readings and Manual Controls")
        readings.pack(fill="x", padx=10, pady=8)
        for row, (name, variable) in enumerate(
            (("Water Level (%)", self._water), ("EC (µS/cm)", self._ec), ("pH", self._ph))
        ):
            ttk.Label(readings, text=name).grid(row=row, column=0, sticky="w", padx=5, pady=3)
            ttk.Label(readings, textvariable=variable).grid(row=row, column=1, sticky="w")
        tk.Button(readings, text="Dose A+B", bg=CAPTURE_COLOR, fg="white", command=lambda: self._ask_dose("FERT")).grid(row=0, column=2, padx=5)
        tk.Button(readings, text="Dose Acid", bg=CAPTURE_COLOR, fg="white", command=lambda: self._ask_dose("ACID")).grid(row=0, column=3, padx=5)
        self._water_button = tk.Button(readings, text="Water OFF", command=self._toggle_water)
        self._water_button.grid(row=1, column=2, padx=5)
        self._light_button = tk.Button(readings, text="Light OFF", command=self._toggle_light)
        self._light_button.grid(row=1, column=3, padx=5)

        settings = ttk.LabelFrame(tab, text="Automation Settings")
        settings.pack(fill="x", padx=10, pady=4)
        for column in range(4):
            settings.columnconfigure(column, weight=1)
        self._light_schedule_label = ttk.Label(
            settings,
            text=(
                f"Light ON Hour: {self._light_on_hour.get()}\n"
                f"Light OFF Hour: {self._light_off_hour.get()}"
            ),
        )
        self._dose_time_label = ttk.Label(
            settings, text=f"Auto Dose (mL): {self._dose_time.get()}"
        )
        self._ec_target_label = ttk.Label(
            settings, text=f"EC Target: {float(self._ec_target.get()):.1f}"
        )
        self._ph_target_label = ttk.Label(
            settings, text=f"pH Target: {float(self._ph_target.get()):.2f}"
        )
        setting_controls = (
            (self._light_schedule_label, self._show_light_schedule_popup),
            (self._dose_time_label, self._show_auto_dose_popup),
            (self._ec_target_label, self._show_ec_target_popup),
            (self._ph_target_label, self._show_ph_target_popup),
        )
        for column, (label, command) in enumerate(setting_controls):
            label.grid(row=0, column=column, sticky="w", padx=5, pady=(5, 0))
            tk.Button(
                settings,
                text="Set",
                command=command,
                bg=CAPTURE_COLOR,
                fg="white",
            ).grid(row=1, column=column, pady=5)

        serial_box = ttk.Frame(tab)
        serial_box.pack(fill="both", expand=True, padx=10, pady=6)
        ttk.Label(serial_box, text="Serial Sent:").grid(row=0, column=0, sticky="w")
        ttk.Label(serial_box, textvariable=self._hydro_sent, relief="groove").grid(row=1, column=0, sticky="ew")
        ttk.Label(serial_box, text="Serial Received:").grid(row=0, column=1, sticky="w")
        ttk.Label(serial_box, textvariable=self._hydro_received, relief="groove").grid(row=1, column=1, sticky="ew")
        serial_box.columnconfigure(0, weight=1)
        serial_box.columnconfigure(1, weight=1)

    def _build_vision_tab(self, tab: ttk.Frame) -> None:
        grid = ttk.Frame(tab)
        grid.pack(fill="both", expand=True, padx=10, pady=8)
        for row, numbers in enumerate(GRID_NUMBERS):
            grid.rowconfigure(row, weight=1)
            for column, plant in enumerate(numbers):
                grid.columnconfigure(column, weight=1)
                cell = ttk.Frame(grid)
                cell.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
                position = position_for_plant(plant)
                button = tk.Button(
                    cell,
                    text=str(plant),
                    bg=GRID_UNSELECTED_COLOR,
                    bd=1,
                    relief="raised",
                    highlightthickness=GRID_BORDER_WIDTH,
                    highlightbackground=GRID_UNSELECTED_COLOR,
                    highlightcolor=GRID_UNSELECTED_COLOR,
                    takefocus=False,
                    command=lambda x=position.x, y=position.y: self._controller.move_to(x, y),
                )
                button.pack(fill="x")
                self._manual_buttons.append(button)
                self._vision_buttons[(position.x, position.y)] = button
                label = ttk.Label(cell, text="No detection", anchor="center", wraplength=110)
                label.pack(fill="both", expand=True)
                self._vision_labels[plant] = label

    # Providers update ApplicationState before queuing each event. Tk consumes
    # up to 200 queued events per poll, so display updates can trail worker state.
    def _drain_events(self) -> None:
        self._assert_main_thread()
        for event in self._controller.ui_events.drain():
            self._handle_event(event)
        if self.root.winfo_exists():
            self.root.after(self._controller.config.gui_poll_interval_ms, self._drain_events)

    def _handle_event(self, event: AppEvent) -> None:
        self._assert_main_thread()
        if event.kind is EventKind.CONNECTION:
            online = bool(event.data.get("online"))
            self._set_online(event.source, online)
            if event.source == "hydroponics":
                self._set_online("light", online)
            elif event.source == "gantry" and not online:
                self._invalidate_position_display()
        elif event.kind is EventKind.GANTRY_RAW:
            self._gantry_raw.set(str(event.data.get("line", "")))
        elif event.kind is EventKind.GANTRY_REQUEST:
            self._invalidate_position_display()
        elif event.kind is EventKind.GANTRY_START:
            if bool(event.data.get("accepted", True)):
                self._mark_position(
                    int(event.data["x"]), int(event.data["y"]), moving=True
                )
        elif event.kind is EventKind.GANTRY_POSITION:
            if bool(event.data.get("accepted", True)):
                x, y = int(event.data["x"]), int(event.data["y"])
                self._mark_position(x, y, moving=False)
                plant = plant_for_xy(x, y)
                self._plant_position.set(f"#{plant}" if plant else "–")
                self._log_message(
                    f"Gantry reached pot {plant}" if plant else f"Gantry at {x},{y}"
                )
        elif event.kind is EventKind.GANTRY_HOME_COMPLETE:
            self._invalidate_position_display()
            self._gantry_state.set("Homed")
        elif event.kind is EventKind.GANTRY_DISABLED:
            self._invalidate_position_display()
            self._gantry_state.set("Disabled")
        elif event.kind is EventKind.GANTRY_TIMEOUT:
            self._invalidate_position_display()
            self._gantry_state.set("Timeout – homing/disable")
        elif event.kind is EventKind.HYDRO_RAW:
            self._hydro_received.set(str(event.data.get("line", "")))
        elif event.kind is EventKind.HYDRO_STATUS:
            status = event.data.get("status")
            if isinstance(status, HydroStatus):
                self._update_hydro(status)
        elif event.kind is EventKind.ARM_STATE:
            self._arm_state.set(str(event.data.get("state", "Unknown")))
        elif event.kind is EventKind.VISION_RESULT:
            result = event.data.get("result")
            if isinstance(result, VisionResult):
                self._show_vision_result(
                    result,
                    auto_close=bool(event.data.get("auto_close", False)),
                )
        elif event.kind is EventKind.AUTOMATION_STATE:
            state = str(event.data.get("state", "unknown"))
            self._log_message(f"Automation: {state}")
            running = state not in ("complete", "stopped", "failed", "idle")
            self._automation_active = running
            self._refresh_control_state()
            self._auto_button.configure(text="Stop" if running else "Auto")
        elif event.kind is EventKind.OPERATION_STATE:
            operation = str(event.data.get("operation", event.source))
            running = bool(event.data.get("running"))
            outcome = str(event.data.get("outcome", "complete"))
            if running:
                self._cancel_operation_release()
                self._exclusive_operation_active = True
                self._refresh_control_state()
            elif self._controller.simulation:
                # Mock workflows can start and finish before one GUI poll.
                # Keep the lock visible briefly so the operator can inspect
                # the same exclusive-control state without slowing tests or
                # changing hardware-mode timing.
                self._schedule_operation_release()
            else:
                self._release_exclusive_operation()
            self._log_message(
                f"{operation}: {'running' if running else outcome}"
            )
        elif event.kind is EventKind.OPERATOR_NOTICE:
            self._show_operator_notice(event)
        elif event.kind is EventKind.LOG:
            message = str(event.data.get("message", ""))
            self._log_message(message)
            if event.source == "hydroponics" and message.startswith("Sent: "):
                self._hydro_sent.set(message[6:])
        elif event.kind is EventKind.ERROR:
            message = str(event.data.get("message", "Unknown error"))
            self._log_message(f"{event.source}: {message}")
            messagebox.showerror(
                self._operator_title(event.source), message, parent=self.root
            )

    def _mark_position(self, x: int, y: int, moving: bool) -> None:
        if self._current_position is not None:
            self._configure_position_buttons(
                self._current_position,
                bg=GRID_UNSELECTED_COLOR,
                bd=1,
                relief="raised",
                highlightbackground=GRID_UNSELECTED_COLOR,
                highlightcolor=GRID_UNSELECTED_COLOR,
            )
        position = (x, y)
        if position in self._grid_buttons:
            self._configure_position_buttons(
                position,
                bg=MOVING_COLOR if moving else GRID_UNSELECTED_COLOR,
                bd=1,
                relief="raised",
                highlightbackground=GRID_SELECTED_BORDER_COLOR,
                highlightcolor=GRID_SELECTED_BORDER_COLOR,
            )
            self._current_position = position
        self._gantry_state.set(f"Moving to {x},{y}" if moving else f"X={x} Y={y}")

    def _configure_position_buttons(
        self,
        position: tuple[int, int],
        **options: object,
    ) -> None:
        for buttons in (self._grid_buttons, self._vision_buttons):
            button = buttons.get(position)
            if button is not None:
                button.configure(**options)

    def _update_hydro(self, status: HydroStatus) -> None:
        self._water.set(f"{max(0.0, min(100.0, status.water_percent)):.1f} %")
        self._ec.set(f"{status.ec:.1f}")
        self._ph.set(f"{status.ph:.2f}")
        self._water_on = status.water_pump_on
        self._light_on = status.light_on
        self._water_button.configure(
            text="Water ON" if self._water_on else "Water OFF",
            bg=MOVEMENT_COLOR if self._water_on else DISABLED_COLOR,
        )
        self._light_button.configure(
            text="Light ON" if self._light_on else "Light OFF",
            bg=MOVING_COLOR if self._light_on else DISABLED_COLOR,
        )
        active = {
            "A": status.fertilizer_on,
            "B": status.fertilizer_on,
            "Acid": status.acid_on,
            "Water": status.water_pump_on,
            "Light": status.light_on,
        }
        for name, enabled in active.items():
            if not enabled:
                color = DISABLED_COLOR
            elif name == "Water":
                color = MOVEMENT_COLOR
            elif name == "Light":
                color = MOVING_COLOR
            else:
                color = ACTION_COLOR
            self._hydro_indicators[name].configure(bg=color)

    def _show_vision_result(self, result: VisionResult, auto_close: bool) -> None:
        self._vision_labels[result.plant].configure(text=result.label)
        self._last_detection.set(result.label)
        self._log_message(f"Plant {result.plant} → {result.label}")
        photo: tk.PhotoImage | None = None
        if result.image_path is None:
            self._last_image.configure(text="Mock detector (no image written)", image="")
        else:
            try:
                photo = tk.PhotoImage(file=str(result.image_path))
                scale = max(1, max(photo.width(), photo.height()) // 400)
                if scale > 1:
                    photo = photo.subsample(scale, scale)
                self._last_photo = photo
                self._last_image.configure(image=photo, text="")
            except tk.TclError:
                self._last_image.configure(text=str(result.image_path), image="")

        # This method is invoked only while the Tk owner drains the UI queue.
        popup = tk.Toplevel(self.root)
        popup.title(f"Plant {result.plant} Inference")
        confidence = (
            f" {result.confidence:.2f}" if result.confidence is not None else ""
        )
        ttk.Label(popup, text=f"Detected: {result.label}{confidence}").pack(
            padx=10, pady=10
        )
        if photo is not None:
            image_label = tk.Label(popup, image=photo)
            image_label.image = photo
            image_label.pack(padx=10, pady=(0, 10))
        elif result.image_path is None:
            ttk.Label(popup, text="Simulation: no image written").pack(
                padx=10, pady=(0, 10)
            )
        else:
            ttk.Label(popup, text=str(result.image_path)).pack(
                padx=10, pady=(0, 10)
            )
        if auto_close:
            popup.after(1000, popup.destroy)

    def _invalidate_position_display(self) -> None:
        if self._current_position is not None:
            self._configure_position_buttons(
                self._current_position,
                bg=GRID_UNSELECTED_COLOR,
                bd=1,
                relief="raised",
                highlightbackground=GRID_UNSELECTED_COLOR,
                highlightcolor=GRID_UNSELECTED_COLOR,
            )
        self._current_position = None
        self._plant_position.set("–")

    def _set_online(self, name: str, online: bool) -> None:
        label = self._status_labels.get(name)
        if label is None:
            return
        title = label.cget("text").split(":", 1)[0]
        label.configure(
            text=f"{title}: {'Online' if online else 'Offline'}",
            bg="#a0e0a0" if online else "#e0a0a0",
        )

    def _set_manual_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self._manual_buttons:
            if button is not self._auto_button:
                button.configure(state=state)

    def _refresh_control_state(self) -> None:
        self._set_manual_enabled(
            not (self._automation_active or self._exclusive_operation_active)
        )
        self._auto_button.configure(
            state="disabled" if self._exclusive_operation_active else "normal"
        )

    def _schedule_operation_release(self) -> None:
        self._cancel_operation_release()
        self._operation_release_after_id = self.root.after(
            SIMULATION_OPERATION_LOCK_MS,
            self._release_exclusive_operation,
        )

    def _cancel_operation_release(self) -> None:
        if self._operation_release_after_id is not None:
            self.root.after_cancel(self._operation_release_after_id)
            self._operation_release_after_id = None

    def _release_exclusive_operation(self) -> None:
        self._operation_release_after_id = None
        self._exclusive_operation_active = False
        self._refresh_control_state()

    def _choose_auto_mode(self) -> None:
        if self._controller.automation_running:
            self._controller.stop_automation()
            return
        popup = tk.Toplevel(self.root)
        popup.title("Auto Mode")
        popup.transient(self.root)
        popup.grab_set()
        ttk.Label(popup, text="Choose automation mode:").pack(padx=20, pady=10)
        tk.Button(
            popup,
            text="Scan Only",
            width=20,
            command=lambda: self._start_automation("scan", popup),
        ).pack(pady=5, ipadx=5)
        tk.Button(
            popup,
            text="Full Auto",
            width=20,
            command=lambda: self._start_automation("full", popup),
        ).pack(pady=(5, 10), ipadx=5)

    def _start_automation(self, mode: AutomationMode, popup: tk.Toplevel) -> None:
        popup.destroy()
        self._controller.start_automation(mode)

    def _ask_dose(self, kind: str) -> None:
        popup = tk.Toplevel(self.root)
        popup.title(f"Set {kind.capitalize()} Dose")
        popup.transient(self.root)
        popup.grab_set()
        amount = tk.IntVar(value=5)
        ttk.Label(popup, text="Dose (mL):").pack(pady=(10, 5))
        ttk.Label(popup, textvariable=amount, font=("Helvetica", 18, "bold")).pack()
        arrows = ttk.Frame(popup)
        arrows.pack(pady=5)
        tk.Button(
            arrows, text="▲", width=3, command=lambda: amount.set(amount.get() + 5)
        ).grid(row=0, column=0, padx=5)
        tk.Button(
            arrows,
            text="▼",
            width=3,
            command=lambda: amount.set(max(5, amount.get() - 5)),
        ).grid(row=0, column=1, padx=5)
        tk.Button(
            popup,
            text="Confirm",
            command=lambda: self._confirm_dose(kind, amount.get(), popup),
            bg=CAPTURE_COLOR,
            fg="white",
        ).pack(pady=(5, 15), ipadx=10)

    def _confirm_dose(self, kind: str, amount: int, popup: tk.Toplevel) -> None:
        try:
            validate_manual_dose_ml(amount)
        except GrowTechError as exc:
            messagebox.showerror("Invalid setting", str(exc), parent=self.root)
            return
        now = time.time()
        last = self._last_dose[kind]
        elapsed_minutes = (now - last) / 60.0 if last else self._dose_lock_minutes
        if elapsed_minutes < self._dose_lock_minutes and not messagebox.askokcancel(
            "Warning",
            f"You dosed {kind.lower()} {elapsed_minutes:.1f} min ago.\nProceed anyway?",
            parent=self.root,
        ):
            return
        try:
            self._controller.dose(kind, amount)
        except GrowTechError as exc:
            messagebox.showerror("Invalid setting", str(exc), parent=self.root)
            return
        # This timestamp records the GUI request, even if the queued write
        # later fails. The 30-minute warning is overridable and not an interlock.
        self._last_dose[kind] = now
        popup.destroy()

    # Toggle feedback is optimistic; a later HydroStatus event replaces it
    # with Nano-reported output state, without a correlated command ACK.
    def _toggle_water(self) -> None:
        new_state = not self._water_on
        self._controller.set_water(new_state)
        self._water_on = new_state
        self._water_button.configure(
            text="Water ON" if new_state else "Water OFF",
            bg=MOVEMENT_COLOR if new_state else DISABLED_COLOR,
        )

    def _toggle_light(self) -> None:
        new_state = not self._light_on
        self._controller.set_light(new_state)
        self._light_on = new_state
        self._light_button.configure(
            text="Light ON" if new_state else "Light OFF",
            bg=MOVEMENT_COLOR if new_state else DISABLED_COLOR,
        )

    def _show_light_schedule_popup(self) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Set Light Schedule")
        popup.transient(self.root)
        popup.grab_set()
        on_hour = tk.IntVar(value=int(self._light_on_hour.get()))
        off_hour = tk.IntVar(value=int(self._light_off_hour.get()))
        for label, variable in (("Auto-ON Hour:", on_hour), ("Auto-OFF Hour:", off_hour)):
            ttk.Label(popup, text=label).pack(pady=(10, 0))
            ttk.Label(
                popup, textvariable=variable, font=("Helvetica", 18, "bold")
            ).pack()
            arrows = ttk.Frame(popup)
            arrows.pack(pady=3)
            tk.Button(
                arrows,
                text="▲",
                width=3,
                command=lambda value=variable: value.set((value.get() + 1) % 24),
            ).grid(row=0, column=0)
            tk.Button(
                arrows,
                text="▼",
                width=3,
                command=lambda value=variable: value.set((value.get() - 1) % 24),
            ).grid(row=0, column=1)

        def confirm() -> None:
            if self._run_input_action(
                lambda: self._controller.set_light_schedule(
                    on_hour.get(), off_hour.get()
                )
            ):
                self._light_on_hour.set(str(on_hour.get()))
                self._light_off_hour.set(str(off_hour.get()))
                self._light_schedule_label.configure(
                    text=(
                        f"Light ON Hour: {on_hour.get()}\n"
                        f"Light OFF Hour: {off_hour.get()}"
                    )
                )
                popup.destroy()

        self._popup_confirm_button(popup, confirm)

    def _show_auto_dose_popup(self) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Set Auto Dose")
        popup.transient(self.root)
        popup.grab_set()
        amount = tk.IntVar(value=int(self._dose_time.get()))
        ttk.Label(popup, text="Auto Dose (mL):").pack(pady=(10, 5))
        self._add_stepped_value(popup, amount, 5, minimum=0)

        def confirm() -> None:
            if self._run_input_action(
                lambda: self._controller.set_dose_time(amount.get())
            ):
                self._dose_time.set(str(amount.get()))
                self._dose_time_label.configure(
                    text=f"Auto Dose (mL): {amount.get()}"
                )
                popup.destroy()

        self._popup_confirm_button(popup, confirm)

    def _show_ec_target_popup(self) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Set EC Target")
        popup.transient(self.root)
        popup.grab_set()
        value = tk.DoubleVar(value=float(self._ec_target.get()))
        ttk.Label(popup, text="EC Target (µS/cm):").pack(pady=(10, 5))
        self._add_stepped_value(popup, value, 100.0, minimum=0.0)

        def confirm() -> None:
            if self._run_input_action(
                lambda: self._controller.set_ec_target(value.get())
            ):
                self._ec_target.set(f"{value.get():.1f}")
                self._ec_target_label.configure(
                    text=f"EC Target: {value.get():.1f}"
                )
                popup.destroy()

        self._popup_confirm_button(popup, confirm)

    def _show_ph_target_popup(self) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Set pH Target")
        popup.transient(self.root)
        popup.grab_set()
        value = tk.DoubleVar(value=float(self._ph_target.get()))
        ttk.Label(popup, text="pH Target:").pack(pady=(10, 5))
        self._add_stepped_value(popup, value, 0.5, minimum=0.0, digits=2)

        def confirm() -> None:
            if self._run_input_action(
                lambda: self._controller.set_ph_target(value.get())
            ):
                self._ph_target.set(f"{value.get():.2f}")
                self._ph_target_label.configure(
                    text=f"pH Target: {value.get():.2f}"
                )
                popup.destroy()

        self._popup_confirm_button(popup, confirm)

    @staticmethod
    def _add_stepped_value(
        popup: tk.Toplevel,
        variable: tk.Variable,
        step: float,
        *,
        minimum: float,
        digits: int | None = None,
    ) -> None:
        ttk.Label(
            popup, textvariable=variable, font=("Helvetica", 18, "bold")
        ).pack()
        arrows = ttk.Frame(popup)
        arrows.pack(pady=3)

        def change(delta: float) -> None:
            result = max(minimum, float(variable.get()) + delta)
            if digits is not None:
                result = round(result, digits)
            variable.set(int(result) if isinstance(variable, tk.IntVar) else result)

        tk.Button(arrows, text="▲", width=3, command=lambda: change(step)).grid(
            row=0, column=0
        )
        tk.Button(arrows, text="▼", width=3, command=lambda: change(-step)).grid(
            row=0, column=1
        )

    @staticmethod
    def _popup_confirm_button(popup: tk.Toplevel, command: Any) -> None:
        tk.Button(
            popup,
            text="Confirm",
            command=command,
            bg=CAPTURE_COLOR,
            fg="white",
        ).pack(pady=(5, 10), ipadx=10)

    def _run_input_action(self, action: Any) -> bool:
        try:
            action()
        except (GrowTechError, TypeError, ValueError) as exc:
            messagebox.showerror("Invalid setting", str(exc), parent=self.root)
            return False
        return True

    def _show_operator_notice(self, event: AppEvent) -> None:
        level = str(event.data.get("level", "info"))
        title = str(event.data.get("title", self._operator_title(event.source)))
        message = str(event.data.get("message", ""))
        self._log_message(f"{event.source}: {message}")
        handler = {
            "warning": messagebox.showwarning,
            "error": messagebox.showerror,
        }.get(level, messagebox.showinfo)
        handler(title, message, parent=self.root)

    @staticmethod
    def _operator_title(source: str) -> str:
        return {
            "arm": "ServoControl",
            "gantry": "Gantry",
            "hydroponics": "Hydroponics",
            "vision": "Camera / Model",
            "automation": "Automation",
            "serial reset": "Serial Reset",
        }.get(source, source.replace("_", " ").title())

    def _log_message(self, message: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", f"• {message}\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _assert_main_thread(self) -> None:
        if threading.get_ident() != self._main_thread_id:
            raise RuntimeError("Tkinter widgets may only be accessed on the GUI thread")

    def _close(self) -> None:
        self._assert_main_thread()
        self._controller.shutdown()
        self.root.destroy()
