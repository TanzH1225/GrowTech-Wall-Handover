"""Explicit GrowTech Wall refactored application entry point.

Hardware dependencies are selected and initialized only after `main()` parses
the mode. Importing this module is therefore safe on a laptop test runner.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import platform
import sys

from config.settings import AppConfig
from utils.errors import HardwareUnavailableError
from utils.logging_config import configure_logging


PI_MODEL_PATHS: tuple[Path, ...] = (
    Path("/proc/device-tree/model"),
    Path("/sys/firmware/devicetree/base/model"),
)


def verify_hardware_platform(
    system: str | None = None,
    machine: str | None = None,
    model_text: str | None = None,
) -> None:
    """Require Linux/aarch64 and Raspberry Pi device-tree evidence."""

    detected_system = system if system is not None else platform.system()
    detected_machine = machine if machine is not None else platform.machine()
    if detected_system != "Linux" or detected_machine.lower() != "aarch64":
        raise HardwareUnavailableError(
            "Hardware mode requires the verified Linux aarch64 Raspberry Pi; "
            "laptop users must run `python app.py --simulate`."
        )
    detected_model = model_text
    if detected_model is None:
        for path in PI_MODEL_PATHS:
            try:
                detected_model = path.read_text(encoding="utf-8", errors="ignore")
                break
            except OSError:
                continue
    if not detected_model or "raspberry pi" not in detected_model.lower():
        raise HardwareUnavailableError(
            "Hardware mode requires Raspberry Pi device-tree model evidence; "
            "use `python app.py --simulate` on an unverified host."
        )


def create_controller(config: AppConfig, simulate: bool):
    """Construct, but do not start, a simulation or hardware runtime."""

    from services.controller import ApplicationController
    from services.events import UiEventQueue
    from services.state import ApplicationEventRouter, ApplicationState

    state = ApplicationState()
    ui_events = UiEventQueue()
    router = ApplicationEventRouter(state, ui_events)

    # Provider selection is explicit: missing hardware never selects simulation.
    if simulate:
        # This branch imports no pyserial, OpenCV, Ultralytics, GPIO, or Pi code.
        from simulation.controllers import (
            MockArmController,
            MockGantryController,
            MockHydroponicsController,
        )
        from simulation.vision import MockVisionService

        gantry = MockGantryController(router.publish)
        hydroponics = MockHydroponicsController(router.publish)
        arm = MockArmController(router.publish)
        vision = MockVisionService()
    else:
        verify_hardware_platform()
        # These modules remain resource-safe at import; `.start()` opens devices.
        from comm.clients import ArmSerialClient, GantrySerialClient, HydroponicsSerialClient
        from vision.hardware import HardwareVisionService

        gantry = GantrySerialClient(config.gantry, router.publish)
        hydroponics = HydroponicsSerialClient(config.hydroponics, router.publish)
        arm = ArmSerialClient(config.arm, router.publish)
        vision = HardwareVisionService(config.vision)

    return ApplicationController(
        config=config,
        state=state,
        ui_events=ui_events,
        router=router,
        gantry=gantry,
        hydroponics=hydroponics,
        arm=arm,
        vision=vision,
        simulation=simulate,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse explicit deployment mode and logging options."""

    parser = argparse.ArgumentParser(description="GrowTech Wall controller")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="use laptop-safe mock controllers and mock vision",
    )
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Start the configured services and Tk main loop."""

    args = parse_args(argv)
    configure_logging(args.verbose)
    try:
        controller = create_controller(AppConfig(), simulate=args.simulate)
    except HardwareUnavailableError as exc:
        print(f"GrowTech Wall startup blocked: {exc}", file=sys.stderr)
        return 2
    try:
        # This is the resource-opening boundary; importing app is not startup.
        controller.start()
        from gui.main_window import GrowTechWindow

        window = GrowTechWindow(controller)
        window.run()
    finally:
        controller.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
