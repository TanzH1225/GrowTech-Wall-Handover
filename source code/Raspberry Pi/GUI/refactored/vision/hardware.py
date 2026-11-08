"""Raspberry Pi camera and Ultralytics implementation.

This module performs no camera/model work at import. The application imports it
only for hardware mode and `start()` performs all resource initialization.
"""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any

from config.settings import VisionConfig
from domain.models import Detection, VisionResult
from utils.errors import HardwareUnavailableError
from vision.logic import image_output_path, roi_bounds, select_best_detection


class HardwareVisionService:
    """Legacy-compatible USB camera capture and YOLO `.pt` inference."""

    def __init__(self, config: VisionConfig) -> None:
        self._config = config
        self._cv2: Any | None = None
        self._model: Any | None = None
        self._camera: Any | None = None
        self._logger = logging.getLogger("vision.hardware")

    def start(self) -> None:
        """Load `bestv5.pt` and open camera index zero explicitly."""

        camera: Any | None = None
        try:
            import cv2  # type: ignore[import-not-found]
            from ultralytics import YOLO  # type: ignore[import-not-found]

            model = YOLO(str(self._config.model_path))
            camera = cv2.VideoCapture(self._config.camera_index)
            if not camera.isOpened():
                raise HardwareUnavailableError(
                    f"Could not open USB camera index {self._config.camera_index}"
                )
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.frame_width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.frame_height)
        except HardwareUnavailableError:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
            raise HardwareUnavailableError(
                f"Could not initialize model {self._config.model_path} or camera: {exc}"
            ) from exc
        self._cv2 = cv2
        self._model = model
        self._camera = camera

    def stop(self) -> None:
        """Release the camera and model references."""

        camera, self._camera = self._camera, None
        if camera is not None:
            camera.release()
        self._model = None
        self._cv2 = None

    def capture(self, plant: int) -> VisionResult:
        """Capture, infer, annotate, and save one plant image."""

        cv2, model, camera = self._cv2, self._model, self._camera
        if cv2 is None or model is None or camera is None:
            raise HardwareUnavailableError("Vision service has not been started")

        time.sleep(self._config.fresh_frame_delay_seconds)
        for _ in range(self._config.stale_frame_grabs):
            camera.grab()
        success, frame = camera.read()
        if not success:
            raise HardwareUnavailableError(f"Camera capture failed for plant {plant}")

        # Convert before drawing on the saved BGR frame, so ROI/detection
        # annotations are not part of the RGB image supplied to inference.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, _ = rgb.shape
        left, right = roi_bounds(
            width,
            self._config.roi_left_fraction,
            self._config.roi_right_fraction,
        )
        cv2.rectangle(frame, (left, 0), (right, height), (255, 0, 0), 2)

        candidates: list[Detection] = []
        try:
            # No crop, resize or explicit model confidence argument is applied
            # here; Ultralytics preprocessing precedes our source-level ROI filter.
            results = model(rgb)
            for box in results[0].boxes:
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                class_id = int(box.cls[0])
                candidates.append(
                    Detection(
                        label=str(model.names[class_id]),
                        confidence=confidence,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )
        except Exception as exc:
            self._logger.exception("YOLO inference failed for plant %s", plant)
            # Preserve the legacy capture behavior: an inference failure is
            # reported, but the ROI-annotated frame is still saved as a
            # no-detection result. Physical validation remains required.
            self._logger.error(
                "Saving plant %s capture with no detection after inference error: %s",
                plant,
                exc,
            )

        best = select_best_detection(
            candidates,
            image_width=width,
            confidence_threshold=self._config.confidence_threshold,
            roi_left_fraction=self._config.roi_left_fraction,
            roi_right_fraction=self._config.roi_right_fraction,
        )
        if best is not None:
            cv2.rectangle(frame, (best.x1, best.y1), (best.x2, best.y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"{best.label} {best.confidence:.2f}",
                (best.x1, best.y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                1,
            )

        output = image_output_path(self._config.image_root, plant, datetime.now())
        output.parent.mkdir(parents=True, exist_ok=True)
        # A false imwrite result becomes an operation error; legacy code only
        # caught exceptions and could announce a save even when it returned false.
        if not cv2.imwrite(str(output), frame):
            raise HardwareUnavailableError(f"Could not save captured image to {output}")
        return VisionResult(
            plant=plant,
            label=best.label if best is not None else "No detection",
            confidence=best.confidence if best is not None else None,
            image_path=output,
        )
