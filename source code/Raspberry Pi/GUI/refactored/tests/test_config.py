from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import AppConfig
from domain.grid import GRID_NUMBERS, SNAKE_SEQUENCE, plant_for_xy, position_for_plant


class ConfigDefaultsTests(unittest.TestCase):
    def test_preserved_endpoint_defaults(self) -> None:
        config = AppConfig()
        self.assertEqual(config.gantry.port, "/dev/arduino_gantry")
        self.assertEqual(config.hydroponics.port, "/dev/arduino_hydroponic")
        self.assertEqual(config.arm.port, "/dev/ttyAMA1")
        self.assertEqual(
            (config.gantry.baud_rate, config.hydroponics.baud_rate, config.arm.baud_rate),
            (9600, 9600, 9600),
        )
        self.assertEqual(config.gantry.timeout_seconds, 1.0)
        self.assertIsNone(config.hydroponics.timeout_seconds)
        self.assertTrue(config.gantry.reset_buffers_on_open)
        self.assertTrue(config.hydroponics.reset_buffers_on_open)
        self.assertFalse(config.arm.reset_buffers_on_open)

    def test_preserved_vision_defaults(self) -> None:
        vision = AppConfig().vision
        self.assertEqual(
            vision.model_path,
            Path(__file__).resolve().parents[2] / "bestv5.pt",
        )
        self.assertEqual(vision.confidence_threshold, 0.3)
        self.assertEqual((vision.roi_left_fraction, vision.roi_right_fraction), (1 / 6, 5 / 6))
        self.assertEqual((vision.camera_index, vision.frame_width, vision.frame_height), (0, 640, 640))
        self.assertEqual(vision.image_root.name, "plant_images")

    def test_grid_and_action_defaults(self) -> None:
        config = AppConfig()
        self.assertEqual(GRID_NUMBERS[-1], (1, 2, 3, 4, 5, 6))
        self.assertEqual(SNAKE_SEQUENCE[:7], (1, 2, 3, 4, 5, 6, 12))
        self.assertEqual(len(SNAKE_SEQUENCE), 24)
        self.assertEqual(position_for_plant(19).x, 1)
        self.assertEqual(position_for_plant(19).y, 4)
        self.assertEqual(plant_for_xy(6, 1), 6)
        self.assertEqual(tuple(config.action_duration(i) for i in range(1, 7)), (4, 4, 5, 7, 1, 10))


if __name__ == "__main__":
    unittest.main()
