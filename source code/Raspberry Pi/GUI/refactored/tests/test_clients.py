from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comm.clients import GantrySerialClient
from config.settings import SerialEndpointConfig
from services.events import AppEvent, EventKind


class SerialClientFailureTests(unittest.TestCase):
    def test_reader_failure_emits_error_and_offline_connection(self) -> None:
        events: list[AppEvent] = []
        client = GantrySerialClient(
            SerialEndpointConfig("fixture", startup_settle_seconds=0), events.append
        )

        class BrokenTransport:
            def read_available(self) -> bytes:
                raise RuntimeError("reader fixture failure")

        client._transport = BrokenTransport()
        with self.assertLogs("comm.gantry", level="ERROR"):
            client._read_loop()
        self.assertTrue(any(event.kind is EventKind.ERROR for event in events))
        offline = [
            event
            for event in events
            if event.kind is EventKind.CONNECTION and not event.data.get("online")
        ]
        self.assertEqual(len(offline), 1)

    def test_start_closes_transport_when_post_open_setup_fails(self) -> None:
        client = GantrySerialClient(
            SerialEndpointConfig("fixture", startup_settle_seconds=0),
            lambda _event: (_ for _ in ()).throw(RuntimeError("sink failure")),
        )

        class Transport:
            def __init__(self) -> None:
                self.opened = False
                self.closed = False

            def open(self) -> None:
                self.opened = True

            def close(self) -> None:
                self.closed = True

            def read_available(self) -> bytes:
                return b""

        transport = Transport()
        client._transport = transport
        with self.assertRaisesRegex(RuntimeError, "sink failure"):
            client.start()
        self.assertTrue(transport.opened)
        self.assertTrue(transport.closed)
        self.assertIsNone(client._thread)

    def test_write_failure_marks_endpoint_offline(self) -> None:
        events: list[AppEvent] = []
        client = GantrySerialClient(
            SerialEndpointConfig("fixture", startup_settle_seconds=0), events.append
        )

        class FailingWriteTransport:
            def write(self, _payload: bytes) -> None:
                raise RuntimeError("write fixture failure")

        client._transport = FailingWriteTransport()
        with self.assertRaisesRegex(RuntimeError, "write fixture failure"):
            client.send("1 1")
        self.assertTrue(
            any(
                event.kind is EventKind.CONNECTION
                and event.source == "gantry"
                and not event.data.get("online")
                for event in events
            )
        )


if __name__ == "__main__":
    unittest.main()
