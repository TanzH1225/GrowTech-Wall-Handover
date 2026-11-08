"""Pure encoders and parsers for preserved controller wire formats."""

from __future__ import annotations

from dataclasses import dataclass
import math

from domain.models import HydroStatus
from utils.errors import ProtocolError


LOBOT_FRAME_HEADER = 0x55
LOBOT_CMD_ACTION_GROUP_RUN = 6
LOBOT_CMD_ACTION_GROUP_STOP = 7


@dataclass(frozen=True)
class GantryReport:
    """Structured interpretation of one source-compatible gantry line."""

    kind: str
    raw: str
    x: int | None = None
    y: int | None = None
    detail: str = ""


def line_command(command: str) -> bytes:
    """Encode a legacy text command with its required newline delimiter."""

    # Framing belongs here; the returned bytes contain the terminating LF.
    # This is command validation, not controller acknowledgement or completion.
    if not command or "\n" in command or "\r" in command:
        raise ProtocolError("Controller command must be one non-empty line")
    return f"{command}\n".encode("utf-8")


def gantry_grid_command(x: int, y: int) -> str:
    """Build the Gantry Nano's `<column> <row>` command."""

    if not 1 <= x <= 6 or not 1 <= y <= 4:
        raise ProtocolError(f"Gantry grid coordinate out of range: {x} {y}")
    return f"{x} {y}"


def gantry_home_command() -> str:
    """Return the legacy full-axis home command."""

    return "0 0"


def gantry_relative_command(direction: str) -> str:
    """Validate a legacy ten-millimetre relative command."""

    normalized = direction.upper()
    if normalized not in ("U", "D", "L", "R"):
        raise ProtocolError(f"Unknown relative direction: {direction}")
    return normalized


def gantry_command_changes_position(command: str) -> bool:
    """Return whether a legacy command invalidates the last confirmed `POS`."""

    stripped = command.strip().upper()
    if stripped in ("0 0", "U", "D", "L", "R", "G", "P", "O"):
        return True
    parts = stripped.split()
    if len(parts) != 2:
        return False
    try:
        x, y = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return 1 <= x <= 6 and 1 <= y <= 4


def hydro_water_command(enabled: bool) -> str:
    return f"WATER_PUMP:{'ON' if enabled else 'OFF'}"


def hydro_light_command(enabled: bool) -> str:
    return f"LIGHT:{'ON' if enabled else 'OFF'}"


def hydro_dose_command(kind: str, millilitres: int) -> str:
    """Build the preserved manual-dose command without adding policy limits."""

    normalized = kind.upper()
    if normalized not in ("ACID", "FERT", "PEST"):
        raise ProtocolError(f"Unknown dose kind: {kind}")
    if isinstance(millilitres, bool) or not isinstance(millilitres, int):
        raise ProtocolError("Dose amount must be a whole number of millilitres")
    if millilitres < 0:
        raise ProtocolError("Dose amount cannot be negative")
    return f"DOSE:{normalized}:{millilitres}"


def hydro_target_ec_command(value: float) -> str:
    validated = validate_ec_target(value)
    return f"TARGET_EC:{validated:.1f}"


def hydro_target_ph_command(value: float) -> str:
    validated = validate_ph_target(value)
    return f"TARGET_PH:{validated:.2f}"


def hydro_light_hour_command(on_hour: int | None = None, off_hour: int | None = None) -> tuple[str, ...]:
    """Build either or both legacy light schedule settings."""

    commands: list[str] = []
    for name, hour in (("LIGHT_ON_HOUR", on_hour), ("LIGHT_OFF_HOUR", off_hour)):
        if hour is None:
            continue
        if not 0 <= hour <= 23:
            raise ProtocolError(f"{name} must be in the range 0..23")
        commands.append(f"{name}:{hour}")
    if not commands:
        raise ProtocolError("At least one light schedule hour is required")
    return tuple(commands)


def hydro_dose_time_command(millilitres: int) -> str:
    validate_auto_dose_ml(millilitres)
    return f"DOSE_TIME:{millilitres}"


def validate_ec_target(value: float) -> float:
    """Validate the legacy GUI's nonnegative 100-unit EC steps."""

    validated = _finite_nonnegative(value, "EC target")
    _require_step(validated, 100.0, "EC target")
    return validated


def validate_ph_target(value: float) -> float:
    """Validate the legacy GUI's nonnegative 0.5-unit pH steps."""

    validated = _finite_nonnegative(value, "pH target")
    _require_step(validated, 0.5, "pH target")
    return validated


def validate_auto_dose_ml(millilitres: int) -> int:
    """Validate the GUI's nonnegative five-millilitre auto-dose steps."""

    _whole_millilitres(millilitres, "Auto dose")
    if millilitres < 0:
        raise ProtocolError("Auto dose cannot be negative")
    if millilitres % 5:
        raise ProtocolError("Auto dose must use 5-mL increments")
    return millilitres


def validate_manual_dose_ml(millilitres: int) -> int:
    """Validate the GUI's manual dose minimum and five-millilitre steps."""

    _whole_millilitres(millilitres, "Manual dose")
    if millilitres < 5:
        raise ProtocolError("Manual dose must be at least 5 mL")
    if millilitres % 5:
        raise ProtocolError("Manual dose must use 5-mL increments")
    return millilitres


def _whole_millilitres(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{label} must be a whole number of millilitres")


def _finite_nonnegative(value: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise ProtocolError(f"{label} must be finite")
    if number < 0:
        raise ProtocolError(f"{label} cannot be negative")
    return number


def _require_step(value: float, step: float, label: str) -> None:
    quotient = value / step
    if not math.isclose(quotient, round(quotient), rel_tol=0.0, abs_tol=1e-9):
        raise ProtocolError(f"{label} must use {step:g}-unit increments")


def arm_group_run_frame(group_id: int, repeat_count: int = 1) -> bytes:
    """Build the exact Lobot action-group frame used by `ServoControl.py`."""

    if not 0 <= group_id <= 255:
        raise ProtocolError("Arm group ID must fit one byte")
    if not 0 <= repeat_count <= 65_535:
        raise ProtocolError("Arm repeat count must fit two bytes")
    # The length byte counts itself, the command and payload, excluding
    # the two header bytes. Repeat count is sent low byte before high byte.
    return bytes(
        (
            LOBOT_FRAME_HEADER,
            LOBOT_FRAME_HEADER,
            5,
            LOBOT_CMD_ACTION_GROUP_RUN,
            group_id,
            repeat_count & 0xFF,
            (repeat_count >> 8) & 0xFF,
        )
    )


def arm_group_stop_frame() -> bytes:
    """Build the exact Lobot stop-action-group frame."""

    return bytes((LOBOT_FRAME_HEADER, LOBOT_FRAME_HEADER, 2, LOBOT_CMD_ACTION_GROUP_STOP))


def parse_gantry_report(line: str) -> GantryReport:
    """Parse structured reports while retaining all descriptive legacy text."""

    stripped = line.strip()
    parts = stripped.split()
    if len(parts) == 3 and parts[0] in ("START", "POS"):
        try:
            return GantryReport(parts[0].lower(), stripped, int(parts[1]), int(parts[2]))
        except ValueError:
            return GantryReport("malformed", stripped, detail="Non-numeric coordinate")
    if stripped.startswith("TIMEOUT:"):
        return GantryReport("timeout", stripped, detail=stripped[8:].strip())
    if "Motors disabled" in stripped:
        return GantryReport("disabled", stripped)
    if stripped == "Homing complete.":
        # Existing source emits this after both startup and `0 0`, but the legacy
        # GUI ignored it and waited forever for a POS record that never arrives.
        return GantryReport("home_complete", stripped)
    if parts and parts[0] == "STATE":
        return GantryReport("state", stripped, detail=" ".join(parts[1:]))
    return GantryReport("text", stripped)


def parse_hydro_status(line: str) -> HydroStatus | None:
    """Parse the legacy status prefix, tolerating future trailing fields."""

    # Positions 5..9 are controller output flags; trailing extension fields
    # are tolerated. Numeric conversion alone does not establish sensor validity.
    parts = line.strip().split(",")
    if len(parts) < 10 or parts[0] != "STAT":
        return None
    if any(value not in ("0", "1") for value in parts[5:10]):
        return None
    try:
        return HydroStatus(
            milliseconds=int(parts[1]),
            water_percent=float(parts[2]),
            ec=float(parts[3]),
            ph=float(parts[4]),
            light_on=parts[5] == "1",
            water_pump_on=parts[6] == "1",
            acid_on=parts[7] == "1",
            fertilizer_on=parts[8] == "1",
            pesticide_on=parts[9] == "1",
        )
    except (TypeError, ValueError):
        return None
