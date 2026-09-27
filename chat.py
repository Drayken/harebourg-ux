"""Turn OCR lines from the anchored combat log into confusion changes.

At turn start every character casts Comtoise on themselves, and the confusion
line printed right next to it is the full angle. The game puts that line just
below the cast, except for the first character's first turn of the fight,
where it comes just above. Any other confusion line comes from a melee hit and
adds 90° horaire, whatever angle it prints.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple

from confusion import Rotation, parse_line

# OCR reads the closing bracket as ), 1 or l: "[14:031 Zxsn". The opening one
# comes out as (, 1 or nothing, and indented lines pick up icon noise in front:
# "117:03] Zxsn", "+ Cl 7:03] Zxsn".
_TIMESTAMP = re.compile(r"^.{0,5}?\d{1,2}\s*[:h.]\s*\d{2}\s*[\])}1l|]")
_PREFIX = re.compile(r"^.{0,5}?\d{1,2}\s*[:h.]\s*\d{2}\s*[\])}1l|]\s*")
_NAME = re.compile(r"[^\s:]+")
# Loose on purpose: OCR spells Confusion as Confflsion or Confision.
_CONFUSION_WORD = re.compile(r"conf|hora|oraire")
_COMTOISE = re.compile(r"\blance\s*:?\s*comt")


class Found(NamedTuple):
    rotation: Rotation
    below: int
    speaker: str | None


class _Line(NamedTuple):
    index: int
    speaker: str | None
    name: str | None
    turn_start: bool
    rotation: Rotation | None


def entries(lines: list[str]) -> list[str]:
    """Join wrapped OCR lines back into log entries.

    With chat timestamps on, a line without one continues the entry above.
    Without timestamps each OCR line is its own entry.
    """

    if not any(_TIMESTAMP.match(line) for line in lines):
        return [line for line in lines if line.strip()]
    joined: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        if _TIMESTAMP.match(line) or not joined:
            joined.append(line)
        else:
            joined[-1] = f"{joined[-1]} {line}"
    return joined


def latest(lines: list[str]) -> Found | None:
    """The angle of whoever has the newest confusion line, from what is visible.

    It needs that character's turn start on screen. If the turn-start line is
    misread, the answer is None rather than an older angle, which would be
    stale and applied as if it were current.
    """

    found = entries(lines)
    confusions = _confusions(found)
    if not confusions:
        return None
    newest = confusions[-1]
    rotation = _since_turn_start(confusions, newest.speaker)
    if rotation is None:
        return None
    return Found(rotation, len(found) - 1 - newest.index, newest.name)


def speaker(entry: str) -> str | None:
    """The character a log entry opens with: "[14:02] Zxsn : Confusion ...".

    A debuff tooltip starts with "Confusion" itself and names nobody.
    """

    match = _NAME.match(_PREFIX.sub("", entry, count=1))
    if match is None or _CONFUSION_WORD.search(_fold(match.group())):
        return None
    return match.group()


def pick(readings: list[list[str]]) -> list[str]:
    """The first OCR reading of the same frame whose newest confusion entry resolves."""

    for lines in readings:
        if latest(lines) is not None:
            return lines
    return readings[0] if readings else []


class Watch:
    """Follows confusion lines as the chat scrolls, and reports each change once.

    Each frame is lined up against the previous one so only entries that were
    not on screen before count as new. That matters because a melee line is a
    change on top of the current angle: counting it twice would be wrong.
    While a character's turn start is visible their angle is recomputed from
    it. Once it scrolls off, new melee lines are added to the remembered angle.
    """

    def __init__(self) -> None:
        self._keys: list[str] = []
        self._angles: dict[str | None, Rotation] = {}
        self._last_speaker: str | None = None

    def reset(self) -> None:
        self._keys = []
        self._angles = {}
        self._last_speaker = None

    def correct(self, rotation: Rotation | None) -> None:
        """A hotkey fixed the angle: later melee lines build on it."""

        if rotation is None:
            self._angles.pop(self._last_speaker, None)
        else:
            self._angles[self._last_speaker] = rotation

    def feed(self, lines: list[str]) -> Found | None:
        found = entries(lines)
        keys = [_key(entry) for entry in found]
        fresh = _first_new(self._keys, keys)
        lined_up = fresh is not None
        if fresh is None:
            fresh = 0
        self._keys = keys
        confusions = _confusions(found)
        new = [line for line in confusions if line.index >= fresh]
        if not new:
            return None
        for who in dict.fromkeys(line.speaker for line in new):
            rotation = self._angle(confusions, new if lined_up else [], who, fresh)
            if rotation is None:
                self._angles.pop(who, None)
            else:
                self._angles[who] = rotation
        newest = new[-1]
        self._last_speaker = newest.speaker
        rotation = self._angles.get(newest.speaker)
        if rotation is None:
            return None
        return Found(rotation, len(found) - 1 - newest.index, newest.name)

    def _angle(self, confusions: list[_Line], new: list[_Line], who: str | None, fresh: int) -> Rotation | None:
        start = _turn_start(confusions, who)
        if start is not None and start.rotation is not None:
            return _since_turn_start(confusions, who)
        if start is not None and start.index >= fresh:
            return None
        rotation = self._angles.get(who)
        if rotation is None:
            return None
        for line in new:
            if line.speaker == who:
                rotation = rotation.bumped()
        return rotation


def _confusions(found: list[str]) -> list[_Line]:
    folded = [_fold(entry) for entry in found]
    names = [speaker(entry) for entry in found]
    speakers = [_who(name) for name in names]
    indexes = [index for index, text in enumerate(folded) if _CONFUSION_WORD.search(text)]
    starts: set[int] = set()
    for index, text in enumerate(folded):
        if not _COMTOISE.search(text):
            continue
        # Above only happens on the fight's first turn. With a line on both sides,
        # the one above is the melee hit that ended the previous turn.
        for neighbor in (index + 1, index - 1):
            if neighbor in indexes and speakers[neighbor] == speakers[index]:
                starts.add(neighbor)
                break
    return [
        _Line(
            index,
            speakers[index],
            names[index],
            index in starts,
            parse_line(found[index]) if index in starts else None,
        )
        for index in indexes
    ]


def _turn_start(confusions: list[_Line], who: str | None) -> _Line | None:
    for line in reversed(confusions):
        if line.speaker == who and line.turn_start:
            return line
    return None


def _since_turn_start(confusions: list[_Line], who: str | None) -> Rotation | None:
    start = _turn_start(confusions, who)
    if start is None or start.rotation is None:
        return None
    rotation = start.rotation
    for line in confusions:
        if line.index > start.index and line.speaker == who:
            rotation = rotation.bumped()
    return rotation


def _first_new(before: list[str], after: list[str]) -> int | None:
    """Where the entries not seen in the previous frame start.

    The previous frame's tail is found in the new one at the spot where it
    overlaps longest. On a tie the earlier spot wins: melee lines repeat the
    same text, so [C] then [C, C] is one new line. None when the frames share
    nothing, so a misread cannot replay melee lines already counted.
    """

    if not before:
        return 0
    best_end, best_length = 0, 0
    for end in range(1, len(after) + 1):
        length = 0
        while length < min(end, len(before)) and before[-1 - length] == after[end - 1 - length]:
            length += 1
        if length > best_length:
            best_end, best_length = end, length
    return best_end if best_length else None


def _key(entry: str) -> str:
    """Compare entries across frames by letters only: OCR shifts digits and punctuation."""

    text = _fold(entry)
    if _CONFUSION_WORD.search(text):
        return f"confusion {_who(speaker(entry)) or ''}"
    return "".join(char for char in text if char.isalpha()).replace("l", "i")


_NAME_LOOKALIKES = str.maketrans({"l": "i", "|": "i", "1": "i", "0": "o"})


def _who(name: str | None) -> str | None:
    """One key per character: OCR reads "Zxsn" as "zxsn" and mixes up l, I and 1."""

    if name is None:
        return None
    return _fold(name).translate(_NAME_LOOKALIKES)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()
