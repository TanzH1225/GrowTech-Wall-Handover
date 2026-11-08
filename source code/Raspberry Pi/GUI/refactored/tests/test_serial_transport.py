from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comm.serial_transport import SerialTransport
from config.settings import SerialEndpointConfig
from utils.errors import HardwareUnavailableError


class SerialTransportLifecycleTests(unittest.TestCase):
    def test_nano_buffers_reset_but_native_arm_uart_does_not(self) -> None:
        handles = []

        class FakeSerial:
            def __init__(self, *_args, **_kwargs) -> None:
                self.is_open = True
                self.input_resets = 0
                self.output_resets = 0
                handles.append(self)

            def reset_input_buffer(self) -> None:
                self.input_resets += 1

            def reset_output_buffer(self) -> None:
                self.output_resets += 1

            def close(self) -> None:
                self.is_open = False

        fake_module = SimpleNamespace(Serial=FakeSerial)
        with patch.dict(sys.modules, {"serial": fake_module}):
            nano = SerialTransport(
                SerialEndpointConfig(
                    "/dev/arduino_gantry",
                    startup_settle_seconds=0,
                    reset_buffers_on_open=True,
                )
            )
            arm = SerialTransport(
                SerialEndpointConfig(
                    "/dev/ttyAMA1",
                    timeout_seconds=None,
                    startup_settle_seconds=0,
                    reset_buffers_on_open=False,
                )
            )
            nano.open()
            arm.open()
            nano.close()
            arm.close()

        self.assertEqual((handles[0].input_resets, handles[0].output_resets), (1, 1))
        self.assertEqual((handles[1].input_resets, handles[1].output_resets), (0, 0))

    def test_open_closes_local_handle_when_post_open_reset_fails(self) -> None:
        handles = []

        class FailingResetSerial:
            def __init__(self, *_args, **_kwargs) -> None:
                self.is_open = True
                self.closed = False
                handles.append(self)

            def reset_input_buffer(self) -> None:
                raise RuntimeError("reset fixture failure")

            def reset_output_buffer(self) -> None:
                raise AssertionError("not reached")

            def close(self) -> None:
                self.closed = True
                self.is_open = False

        fake_module = SimpleNamespace(Serial=FailingResetSerial)
        transport = SerialTransport(
            SerialEndpointConfig(
                "/dev/arduino_gantry",
                startup_settle_seconds=0,
                reset_buffers_on_open=True,
            )
        )
        with patch.dict(sys.modules, {"serial": fake_module}):
            with self.assertRaises(HardwareUnavailableError):
                transport.open()
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)
        self.assertFalse(transport.is_open)


if __name__ == "__main__":
    unittest.main()
