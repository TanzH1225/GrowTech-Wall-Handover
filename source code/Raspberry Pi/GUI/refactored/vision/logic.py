"""Dependency-free legacy ROI, selection, and image-path behavior."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import math
from typing import Iterable

from domain.models import Detection


def roi_bounds(
    width: int,
    left_fraction: float = 1.0 / 6.0,
    right_fraction: float = 5.0 / 6.0,
) -> tuple[int, int]:
    """Return the inclusive central-two-thirds bounds used by legacy source."""

    if width <= 0:
        raise ValueError("Image width must be positive")
    if (
        not math.isfinite(left_fraction)
        or not math.isfinite(right_fraction)
        or not 0.0 <= left_fraction < right_fraction <= 1.0
    ):
        raise ValueError("ROI fractions must satisfy 0 <= left < right <= 1")
    return int(width * left_fraction), int(width * right_fraction)


def select_best_detection(
    detections: Iterable[Detection],
    image_width: int,
    confidence_threshold: float = 0.3,
    roi_left_fraction: float = 1.0 / 6.0,
    roi_right_fraction: float = 5.0 / 6.0,
) -> Detection | None:
    """Filter by confidence/ROI and select the highest-confidence detection."""

    left, right = roi_bounds(
        image_width,
        left_fraction=roi_left_fraction,
        right_fraction=roi_right_fraction,
    )
    # ROI means the horizontal center is inside inclusive bounds; the box
    # need not fit inside the ROI. The full image still reaches the model.
    eligible = (
        detection
        for detection in detections
        if detection.confidence >= confidence_threshold
        and left <= detection.center_x <= right
    )
    # Equal confidence keeps the first eligible item in model iteration order.
    return max(eligible, key=lambda item: item.confidence, default=None)


def image_output_path(root: Path, plant: int, captured_at: datetime) -> Path:
    """Build `~/plant_images/<plant>/<YYYYmmdd_HHMMSS>.png`."""

    if not 1 <= plant <= 24:
        raise ValueError(f"Plant must be in the range 1..24, got {plant}")
    # Names have second precision; repeated captures in the same second can
    # select the same path. This helper builds a path without writing any image.
    return root.expanduser() / str(plant) / f"{captured_at:%Y%m%d_%H%M%S}.png"
