"""Legacy 24-position plant-grid mapping."""

from __future__ import annotations

from dataclasses import dataclass


# GUI rows run top-to-bottom; Nano Y and plant numbering rise from the bottom.
GRID_NUMBERS: tuple[tuple[int, ...], ...] = (
    (19, 20, 21, 22, 23, 24),
    (13, 14, 15, 16, 17, 18),
    (7, 8, 9, 10, 11, 12),
    (1, 2, 3, 4, 5, 6),
)

SNAKE_SEQUENCE: tuple[int, ...] = (
    1, 2, 3, 4, 5, 6,
    12, 11, 10, 9, 8, 7,
    13, 14, 15, 16, 17, 18,
    24, 23, 22, 21, 20, 19,
)


@dataclass(frozen=True)
class GridPosition:
    """One plant's GUI row/column and Gantry Nano X/Y coordinate."""

    plant: int
    gui_row: int
    gui_column: int
    x: int
    y: int


def position_for_plant(plant: int) -> GridPosition:
    """Convert a 1-based plant number to its preserved grid coordinate."""

    for gui_row, row in enumerate(GRID_NUMBERS):
        for gui_column, candidate in enumerate(row):
            if candidate == plant:
                return GridPosition(
                    plant=plant,
                    gui_row=gui_row,
                    gui_column=gui_column,
                    x=gui_column + 1,
                    y=4 - gui_row,
                )
    raise ValueError(f"Plant must be in the range 1..24, got {plant}")


def plant_for_xy(x: int, y: int) -> int | None:
    """Return the plant number for a valid Gantry Nano grid coordinate."""

    if not 1 <= x <= 6 or not 1 <= y <= 4:
        return None
    return GRID_NUMBERS[4 - y][x - 1]
