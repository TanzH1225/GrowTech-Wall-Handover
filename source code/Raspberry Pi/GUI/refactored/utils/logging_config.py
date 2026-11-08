"""Central logging setup without file-system side effects."""

from __future__ import annotations

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configure concise console logging when the explicit entry point runs."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
