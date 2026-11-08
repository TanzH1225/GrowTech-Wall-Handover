"""Immutable defaults derived from the preserved legacy deployment."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SerialEndpointConfig:
    """Configuration for one controller transport."""

    port: str
    baud_rate: int = 9600
    timeout_seconds: float | None = 1.0
    startup_settle_seconds: float = 2.0
    reset_buffers_on_open: bool = True


@dataclass(frozen=True)
class VisionConfig:
    """Legacy camera, model, filtering, and image-store defaults."""

    # Portable handover copy: use the included model beside this GUI.
    model_path: Path = Path(__file__).resolve().parents[2] / "bestv5.pt"
    confidence_threshold: float = 0.3
    roi_left_fraction: float = 1.0 / 6.0
    roi_right_fraction: float = 5.0 / 6.0
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 640
    stale_frame_grabs: int = 5
    fresh_frame_delay_seconds: float = 0.2
    image_root: Path = field(
        default_factory=lambda: Path("~/plant_images").expanduser()
    )


@dataclass(frozen=True)
class ArmActionConfig:
    """A legacy action-group identifier and its fixed assumed duration."""

    group_id: int
    duration_seconds: float
    description: str


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration with preserved legacy defaults."""

    gantry: SerialEndpointConfig = field(
        default_factory=lambda: SerialEndpointConfig(
            port="/dev/arduino_gantry", timeout_seconds=1.0
        )
    )
    # Nano defaults settle/reset on open; the native arm overrides both below.
    hydroponics: SerialEndpointConfig = field(
        default_factory=lambda: SerialEndpointConfig(
            port="/dev/arduino_hydroponic", timeout_seconds=None
        )
    )
    arm: SerialEndpointConfig = field(
        default_factory=lambda: SerialEndpointConfig(
            port="/dev/ttyAMA1",
            timeout_seconds=None,
            startup_settle_seconds=0.0,
            reset_buffers_on_open=False,
        )
    )
    vision: VisionConfig = field(default_factory=VisionConfig)
    # Durations are assumed Pi waits, not acknowledgements from the arm board.
    arm_actions: tuple[ArmActionConfig, ...] = (
        ArmActionConfig(1, 4.0, "Harvest pick-up"),
        ArmActionConfig(2, 4.0, "Rotate and store in basket"),
        ArmActionConfig(3, 5.0, "Pick new seedling from rack"),
        ArmActionConfig(4, 7.0, "Plant seedling into spot"),
        ArmActionConfig(5, 1.0, "Return to idle / camera mode"),
        ArmActionConfig(6, 10.0, "Pesticide spray"),
    )
    pesticide_dose_ml: int = 11
    seedling_rack_plant: int = 6
    gui_poll_interval_ms: int = 50

    def action_duration(self, group_id: int) -> float:
        """Return the source-verified fixed wait for an arm group."""

        for action in self.arm_actions:
            if action.group_id == group_id:
                return action.duration_seconds
        raise ValueError(f"Unknown arm action group: {group_id}")
