from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import VisionConfig
from domain.models import Detection
from utils.errors import HardwareUnavailableError
from vision.hardware import HardwareVisionService
from vision.logic import image_output_path, roi_bounds, select_best_detection


class VisionLogicTests(unittest.TestCase):
    def test_central_two_thirds_filter_and_best_selection(self) -> None:
        self.assertEqual(roi_bounds(600), (100, 500))
        detections = (
            Detection("outside", 0.99, 0, 0, 20, 20),
            Detection("weak", 0.29, 200, 0, 300, 50),
            Detection("eligible", 0.80, 250, 0, 350, 50),
            Detection("best", 0.90, 400, 0, 500, 50),
        )
        best = select_best_detection(detections, 600, 0.3)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.label, "best")

    def test_configured_roi_fractions_drive_selection(self) -> None:
        self.assertEqual(roi_bounds(400, 0.25, 0.75), (100, 300))
        detections = (
            Detection("outside-custom", 0.99, 40, 0, 80, 40),
            Detection("inside-custom", 0.80, 180, 0, 220, 40),
        )
        best = select_best_detection(
            detections,
            image_width=400,
            confidence_threshold=0.3,
            roi_left_fraction=0.25,
            roi_right_fraction=0.75,
        )
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.label, "inside-custom")
        with self.assertRaises(ValueError):
            roi_bounds(400, 0.8, 0.2)

    def test_image_path_preserves_plant_and_timestamp_layout(self) -> None:
        path = image_output_path(Path("/tmp/plant_images"), 7, datetime(2026, 7, 18, 13, 4, 5))
        self.assertEqual(path, Path("/tmp/plant_images/7/20260718_130405.png"))

    def test_inference_error_still_saves_no_detection_capture(self) -> None:
        class Frame:
            shape = (640, 640, 3)

        class Camera:
            def read(self):
                return True, Frame()

            def grab(self):
                return True

            def release(self):
                return None

        class BrokenModel:
            def __call__(self, _image):
                raise RuntimeError("fixture inference failure")

        class FakeCv2:
            COLOR_BGR2RGB = 1
            FONT_HERSHEY_SIMPLEX = 2

            def __init__(self):
                self.saved: list[str] = []

            def cvtColor(self, frame, _mode):
                return frame

            def rectangle(self, *_args):
                return None

            def putText(self, *_args):
                return None

            def imwrite(self, path, _frame):
                self.saved.append(path)
                return True

        with TemporaryDirectory() as temp:
            config = VisionConfig(
                image_root=Path(temp),
                stale_frame_grabs=0,
                fresh_frame_delay_seconds=0,
            )
            service = HardwareVisionService(config)
            fake_cv2 = FakeCv2()
            service._cv2 = fake_cv2
            service._model = BrokenModel()
            service._camera = Camera()
            with self.assertLogs("vision.hardware", level="ERROR"):
                result = service.capture(3)
            self.assertEqual(result.label, "No detection")
            self.assertEqual(len(fake_cv2.saved), 1)
            self.assertIn(str(Path(temp) / "3"), fake_cv2.saved[0])

    def test_start_releases_camera_after_post_open_failure(self) -> None:
        class Camera:
            def __init__(self) -> None:
                self.releases = 0

            def isOpened(self) -> bool:
                return True

            def set(self, *_args) -> None:
                raise RuntimeError("camera configuration fixture failure")

            def release(self) -> None:
                self.releases += 1

        camera = Camera()
        fake_cv2 = SimpleNamespace(
            VideoCapture=lambda _index: camera,
            CAP_PROP_FRAME_WIDTH=1,
            CAP_PROP_FRAME_HEIGHT=2,
        )
        fake_ultralytics = SimpleNamespace(YOLO=lambda _path: object())
        service = HardwareVisionService(VisionConfig())
        with patch.dict(
            sys.modules,
            {"cv2": fake_cv2, "ultralytics": fake_ultralytics},
        ):
            with self.assertRaisesRegex(
                HardwareUnavailableError, "camera configuration fixture failure"
            ):
                service.start()
        self.assertEqual(camera.releases, 1)


if __name__ == "__main__":
    unittest.main()
