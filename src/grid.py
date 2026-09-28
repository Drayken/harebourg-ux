"""Map cell lists, iso projection, and hit testing.

Cells use square grid coordinates: x is the column (east), y is the row
(south). The board is that square grid turned 45° clockwise and squashed to
half height, so rotations from `confusion` apply to (x, y) unchanged.

Map files in `maps/` hold one character per cell, one line per row:

    .  walkable
    #  wall
    -  empty
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

MAPS_DIR = Path(__file__).resolve().parent / "maps"

Cell = tuple[int, int]


class Kind(Enum):
    EMPTY = "-"
    WALKABLE = "."
    WALL = "#"


_SITE_KINDS = {1: Kind.WALKABLE, 2: Kind.WALL}


@dataclass(frozen=True)
class Layout:
    name: str
    rows: tuple[tuple[Kind, ...], ...]

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    def kind(self, cell: Cell) -> Kind:
        x, y = cell
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.rows[y][x]
        return Kind.EMPTY

    def contains(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= y < self.height and 0 <= x < self.width

    def walkable(self, cell: Cell) -> bool:
        return self.kind(cell) is Kind.WALKABLE

    def is_hole(self, cell: Cell) -> bool:
        """An empty cell inside the board, between used cells on its row."""

        x, y = cell
        if self.kind(cell) is not Kind.EMPTY or not 0 <= y < self.height:
            return False
        row = self.rows[y]
        left = any(kind is not Kind.EMPTY for kind in row[:x])
        right = any(kind is not Kind.EMPTY for kind in row[x + 1 :])
        return left and right

    def cells(self) -> list[tuple[Cell, Kind]]:
        return [((x, y), kind) for y, row in enumerate(self.rows) for x, kind in enumerate(row)]

    def to_text(self) -> str:
        return "\n".join("".join(kind.value for kind in row) for row in self.rows) + "\n"


def parse_text(name: str, text: str) -> Layout:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"carte {name!r} vide")
    width = max(len(line) for line in lines)
    rows = []
    for number, line in enumerate(lines, start=1):
        try:
            rows.append(tuple(Kind(char) for char in line.ljust(width, Kind.EMPTY.value)))
        except ValueError as exc:
            raise ValueError(f"carte {name!r} ligne {number} : {exc}") from None
    return Layout(name, tuple(rows))


def parse_site_layout(name: str, text: str) -> Layout:
    """Read the map string a player copies from the simulator's Edit mode.

    Format: {"size": [rows, cols], "details": [[row, first_col, last_col, type], ...]}
    with type 1 for walkable and 2 for wall.
    """

    data = json.loads(text)
    height, width = (int(value) for value in data["size"])
    grid = [[Kind.EMPTY] * width for _ in range(height)]
    for row, first, last, code in data["details"]:
        kind = _SITE_KINDS.get(int(code))
        if kind is None:
            raise ValueError(f"type de case inconnu {code} à la ligne {row}")
        if not 0 <= row < height or not 0 <= first <= last < width:
            raise ValueError(f"plage {row}:{first}-{last} hors de {height}x{width}")
        for x in range(first, last + 1):
            grid[row][x] = kind
    return Layout(name, tuple(tuple(row) for row in grid))


def load_map(name: str) -> Layout:
    path = MAPS_DIR / f"{name}.txt"
    return parse_text(name, path.read_text(encoding="utf-8"))


def available_maps() -> list[str]:
    return sorted(path.stem for path in MAPS_DIR.glob("*.txt"))


@dataclass(frozen=True)
class Projection:
    """Screen placement of a layout. Origin is the center of cell (0, 0)."""

    origin_x: float
    origin_y: float
    cell_width: float
    cell_height: float

    def center(self, cell: Cell) -> tuple[float, float]:
        return self._point(cell[0], cell[1])

    def diamond(self, cell: Cell) -> tuple[tuple[int, int], ...]:
        """Top, right, bottom, left corners, rounded to whole pixels.

        Corners are the projected grid-line crossings, so neighbouring cells
        share the exact same vertices and never gap or overlap.
        """

        x, y = cell
        corners = (
            self._point(x - 0.5, y - 0.5),
            self._point(x + 0.5, y - 0.5),
            self._point(x + 0.5, y + 0.5),
            self._point(x - 0.5, y + 0.5),
        )
        # floor(v + 0.5), not round(): banker's rounding would make a 1 px
        # nudge move some edges by 0 and others by 2.
        return tuple((math.floor(sx + 0.5), math.floor(sy + 0.5)) for sx, sy in corners)

    def cell_at(self, screen_x: float, screen_y: float) -> Cell:
        u = (screen_x - self.origin_x) / (self.cell_width / 2)
        v = (screen_y - self.origin_y) / (self.cell_height / 2)
        return round((v + u) / 2), round((v - u) / 2)

    def bounds(self, layout: Layout) -> tuple[int, int, int, int] | None:
        """Left, top, right, bottom of the used cells' diamonds."""

        corners = [
            corner
            for cell, kind in layout.cells()
            if kind is not Kind.EMPTY
            for corner in self.diamond(cell)
        ]
        if not corners:
            return None
        xs = [x for x, _ in corners]
        ys = [y for _, y in corners]
        return min(xs), min(ys), max(xs), max(ys)

    def moved(self, dx: float, dy: float) -> Projection:
        return Projection(self.origin_x + dx, self.origin_y + dy, self.cell_width, self.cell_height)

    def scaled(self, sx: float, sy: float, anchor_x: float, anchor_y: float) -> Projection:
        """Stretch the whole grid about a screen point, which stays put."""

        return Projection(
            anchor_x + (self.origin_x - anchor_x) * sx,
            anchor_y + (self.origin_y - anchor_y) * sy,
            self.cell_width * sx,
            self.cell_height * sy,
        )

    def scaled_uniform(self, factor: float, anchor_x: float, anchor_y: float) -> Projection:
        """Scale about a screen point. Floor diamonds stay twice as wide as they are tall."""

        new_width = self.cell_width * factor
        new_height = new_width / 2
        u = (anchor_x - self.origin_x) / (self.cell_width / 2)
        v = (anchor_y - self.origin_y) / (self.cell_height / 2)
        return Projection(
            anchor_x - u * (new_width / 2),
            anchor_y - v * (new_height / 2),
            new_width,
            new_height,
        )

    def fit(self, layout: Layout, width: int, height: int, margin: float = 0) -> Projection:
        """Same cell shape, centered on the used cells of `layout` in a width x height box."""

        used = [cell for cell, kind in layout.cells() if kind is not Kind.EMPTY]
        if not used:
            return self
        xs = [self._point(x, y)[0] - self.origin_x for x, y in used]
        ys = [self._point(x, y)[1] - self.origin_y for x, y in used]
        mid_x = (min(xs) + max(xs)) / 2
        mid_y = (min(ys) + max(ys)) / 2
        span_x = max(xs) - min(xs) + self.cell_width
        span_y = max(ys) - min(ys) + self.cell_height
        shrink = min(1.0, (width - margin * 2) / span_x, (height - margin * 2) / span_y)
        cell_width = self.cell_width * shrink
        cell_height = self.cell_height * shrink
        return Projection(
            round(width / 2 - mid_x * shrink),
            round(height / 2 - mid_y * shrink),
            cell_width,
            cell_height,
        )

    def _point(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.origin_x + (x - y) * (self.cell_width / 2),
            self.origin_y + (x + y) * (self.cell_height / 2),
        )
