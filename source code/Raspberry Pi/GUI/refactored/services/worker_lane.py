"""Small ordered daemon worker lanes with bounded shutdown semantics."""

from __future__ import annotations

from collections.abc import Callable
from queue import Empty, Queue
import threading


class OrderedWorkerLane:
    """Execute submitted callables in order on one daemon worker thread.

    Daemon ownership prevents a permanently blocked third-party I/O call from
    retaining CPython at process exit. Normal shutdown still stops providers and
    joins each lane within the controller's shared bounded deadline.
    """

    _SENTINEL = object()

    def __init__(self, name: str) -> None:
        self._queue: Queue[Callable[[], object] | object] = Queue()
        self._lock = threading.Lock()
        self._accepting = True
        self._thread = threading.Thread(
            target=self._run,
            name=f"growtech-{name}",
            daemon=True,
        )
        self._thread.start()

    def submit(self, action: Callable[[], object]) -> bool:
        """Queue one action if shutdown has not closed the lane."""

        with self._lock:
            if not self._accepting:
                return False
            self._queue.put(action)
            return True

    def close(self, cancel_pending: bool = True) -> None:
        """Stop accepting work and optionally discard actions not yet started."""

        with self._lock:
            if not self._accepting:
                return
            self._accepting = False
            # Discard queued jobs only. The currently executing callable must
            # observe controller cancellation or return from its provider I/O.
            if cancel_pending:
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except Empty:
                        break
                    else:
                        self._queue.task_done()
                        if item is self._SENTINEL:
                            break
            self._queue.put(self._SENTINEL)

    def join(self, timeout: float) -> bool:
        """Wait at most *timeout* seconds; return whether the worker exited."""

        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._SENTINEL:
                    return
                assert callable(item)
                item()
            finally:
                self._queue.task_done()
