"""Transport-independent application values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Detection:
    """One model detection in full-frame pixel coordinates."""

    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center_x(self) -> int:
        """Horizontal bounding-box center used by the legacy ROI filter."""

        return (self.x1 + self.x2) // 2


@dataclass(frozen=True)
class VisionResult:
    """Result of one plant capture and inference operation."""

    plant: int
    label: str
    confidence: float | None
    image_path: Path | None


@dataclass(frozen=True)
class HydroStatus:
    """One complete ten-field `STAT` record from the Hydroponics Nano."""

    milliseconds: int
    water_percent: float
    ec: float
    ph: float
    light_on: bool
    water_pump_on: bool
    acid_on: bool
    fertilizer_on: bool
    pesticide_on: bool
