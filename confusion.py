"""Harebourg confusion states.

Turn start is one of three redirects. A melee damage line adds 90° horaire
to that redirect, which can also land on 0°.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum


class Rotation(Enum):
    """Degrees in the game's "horaire" sense, as the combat log names them."""

    STRAIGHT = 0
    CLOCKWISE = 90
    HALF = 180
    COUNTERCLOCKWISE = 270

    @property
    def clockwise_degrees(self) -> int:
        return int(self.value)

    def bumped(self) -> Rotation:
        return Rotation((self.clockwise_degrees + 90) % 360)

    @property
    def inverse(self) -> Rotation:
        return Rotation((360 - self.clockwise_degrees) % 360)

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    Rotation.STRAIGHT: "Tout droit",
    Rotation.CLOCKWISE: "90° horaire",
    Rotation.HALF: "180°",
    Rotation.COUNTERCLOCKWISE: "90° contre horaire",
}

_SHORT_LABELS = {
    Rotation.STRAIGHT: "Droit",
    Rotation.CLOCKWISE: "90° hor.",
    Rotation.HALF: "180°",
    Rotation.COUNTERCLOCKWISE: "90° contre",
}


def short_label(rotation: Rotation) -> str:
    return _SHORT_LABELS[rotation]


# Turn-start redirect by the player's own life, from full to empty. Each entry is the
# lowest life % of the band and the redirect it gives.
PHASES: tuple[tuple[int, Rotation], ...] = (
    (90, Rotation.CLOCKWISE),
    (75, Rotation.COUNTERCLOCKWISE),
    (45, Rotation.HALF),
    (30, Rotation.COUNTERCLOCKWISE),
    (0, Rotation.CLOCKWISE),
)

_DIRECTION = r"(?P<direction>contre[\s-]*horaire|horaire)"
# Windows OCR reads π as TT, Tt or Ti, and a small 1 as I or l.
_OCR_DIGIT = r"[\d|]|\b[il](?=\s*(?:pi|tt|ti|t1|tl|rr|rt|n)\s*/)"
_PI = rf"(?P<num>(?:{_OCR_DIGIT})+)\s*(?:pi|tt|ti|t1|tl|rr|rt|n)\s*/\s*(?P<den>[\dil|]+)\b"
_DEGREES = r"(?P<deg>\d+)\s*degres"
# OCR also turns "90°" into "900". Only the three real angles are read this way.
_OCR_DEGREES = r"\b(?P<deg>90|180|270)[0o]?"
_PATTERNS = (
    re.compile(rf"{_DIRECTION}\s*:?\s*{_PI}"),
    re.compile(rf"{_DIRECTION}\s*:?\s*{_DEGREES}"),
    re.compile(rf"{_PI}\s*{_DIRECTION}"),
    re.compile(rf"{_DEGREES}\s*{_DIRECTION}"),
    re.compile(rf"{_OCR_DEGREES}\s*{_DIRECTION}"),
)
_OCR_ONE = str.maketrans({"i": "1", "l": "1", "|": "1"})


def rotate_offset(dx: int, dy: int, rotation: Rotation) -> tuple[int, int]:
    """Turn a cell offset the way the game does. +x is east, +y is south.

    Horaire turns the landing clockwise on screen. On the cheat sheet, 90°
    horaire (also "270° contre horaire") puts the click on the caster's left
    when the monster is straight above. The other side lands behind the caster.
    """

    x, y = dx, dy
    for _ in range(rotation.clockwise_degrees // 90):
        x, y = -y, x
    return x, y


def landing_cell(
    origin: tuple[int, int],
    cursor: tuple[int, int],
    rotation: Rotation,
) -> tuple[int, int]:
    dx, dy = cursor[0] - origin[0], cursor[1] - origin[1]
    rx, ry = rotate_offset(dx, dy, rotation)
    return origin[0] + rx, origin[1] + ry


def aim_cell(
    origin: tuple[int, int],
    desired: tuple[int, int],
    rotation: Rotation,
) -> tuple[int, int]:
    """The cell to click so the spell lands on `desired`."""

    return landing_cell(origin, desired, rotation.inverse)


def parse_line(text: str) -> Rotation | None:
    """Return the redirect described by one combat-log line."""

    normalized = _normalize(text)
    for pattern in _PATTERNS:
        match = pattern.search(normalized)
        if match is None:
            continue
        rotation = _rotation_from_match(match)
        if rotation is not None:
            return rotation
    return None


def _normalize(text: str) -> str:
    text = text.replace("π", "pi").replace("Π", "pi").replace("°", " degres ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold()


def _rotation_from_match(match: re.Match[str]) -> Rotation | None:
    groups = match.groupdict()
    if groups.get("deg") is not None:
        degrees = int(groups["deg"])
    else:
        numerator = int(groups["num"].translate(_OCR_ONE))
        denominator = int(groups["den"].translate(_OCR_ONE))
        if denominator == 0:
            return None
        degrees = numerator * 180 // denominator
    # The game prints 90°, 180° or 270° (1π/2 to 6π/4). Anything outside is a misread
    # digit, like 3π/2 read as 8π/2 or 5π/2, and would light the wrong cells.
    if not 0 < degrees < 360:
        return None
    if match.group("direction").startswith("contre"):
        degrees = 360 - degrees
    try:
        return Rotation(degrees)
    except ValueError:
        return None
