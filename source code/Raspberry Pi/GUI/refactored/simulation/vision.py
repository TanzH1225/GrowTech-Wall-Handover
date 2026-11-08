"""Deterministic mock detector with no camera/model imports or file writes."""

from __future__ import annotations

import threading

from domain.models import VisionResult


class MockVisionService:
    """Return configured labels, defaulting to a varied 24-plant fixture."""

    def __init__(self, labels: dict[int, str] | None = None) -> None:
        self._labels = dict(labels or {})
        self._captures: list[int] = []
        self._lock = threading.Lock()
        self._started = False

    @property
    def captures(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(self._captures)

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def capture(self, plant: int) -> VisionResult:
        if not self._started:
            raise RuntimeError("Mock vision service has not been started")
        with self._lock:
            self._captures.append(plant)
        default_label = (
            "Matured" if plant % 8 == 0 else "Immatured" if plant % 5 == 0 else "No detection"
        )
        label = self._labels.get(plant, default_label)
        return VisionResult(
            plant=plant,
            label=label,
            confidence=None if label == "No detection" else 0.90,
            image_path=None,
        )
