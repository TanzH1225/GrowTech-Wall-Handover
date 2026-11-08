"""Application-specific exceptions with operator-facing context."""


class GrowTechError(Exception):
    """Base class for expected GrowTech Wall application errors."""


class HardwareUnavailableError(GrowTechError):
    """Raised when a requested hardware endpoint cannot be initialized."""


class ProtocolError(GrowTechError):
    """Raised when a command cannot be encoded safely."""
