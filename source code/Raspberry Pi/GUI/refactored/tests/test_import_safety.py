from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ImportSafetyTests(unittest.TestCase):
    def test_import_and_simulation_factory_do_not_import_hardware_or_tk(self) -> None:
        project = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            import builtins
            import sys

            blocked = {"serial", "cv2", "ultralytics", "tkinter", "RPi", "gpiozero"}
            original_import = builtins.__import__

            def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name.split(".", 1)[0] in blocked:
                    raise AssertionError(f"unexpected import: {name}")
                return original_import(name, globals, locals, fromlist, level)

            builtins.__import__ = guarded_import
            import app
            from config.settings import AppConfig
            controller = app.create_controller(AppConfig(), simulate=True)
            controller.start()
            controller.shutdown()
            assert not (blocked & set(sys.modules)), blocked & set(sys.modules)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
