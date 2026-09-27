"""Rebindable keys for the two cell actions: mark your cell and pin a target.

A bind is a mouse button (3 middle, 4, 5) or a keyboard key with optional
Ctrl/Maj/Alt. Left and right buttons always stay with the game.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MODS = MOD_ALT | MOD_CONTROL | MOD_SHIFT

MOUSE_BUTTONS = (3, 4, 5)

MARK_SELF = "mark_self"
PIN = "pin"
ACTIONS = (MARK_SELF, PIN)
ACTION_NAMES = {MARK_SELF: "Marquer ma case", PIN: "Épingler la cible"}

VK_ESCAPE = 0x1B

# Shift, Ctrl, Alt (generic, left, right) and both Windows keys.
MODIFIER_KEYS = frozenset({0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C})

_NAMES = {
    0x08: "Retour",
    0x09: "Tab",
    0x0D: "Entrée",
    0x13: "Pause",
    0x14: "Verr. maj",
    0x20: "Espace",
    0x21: "Pg préc",
    0x22: "Pg suiv",
    0x23: "Fin",
    0x24: "Origine",
    0x25: "Gauche",
    0x26: "Haut",
    0x27: "Droite",
    0x28: "Bas",
    0x2C: "Impr. écran",
    0x2D: "Inser",
    0x2E: "Suppr",
    0x6A: "Pavé *",
    0x6B: "Pavé +",
    0x6D: "Pavé -",
    0x6E: "Pavé .",
    0x6F: "Pavé /",
    0x91: "Arrêt défil",
}
_NAMES.update({vk: chr(vk) for vk in range(0x30, 0x3A)})
_NAMES.update({vk: chr(vk) for vk in range(0x41, 0x5B)})
_NAMES.update({0x60 + n: f"Pavé {n}" for n in range(10)})
_NAMES.update({0x70 + n: f"F{n + 1}" for n in range(24)})

# Keys that do not type text, so they can be taken without a modifier.
FREE_KEYS = frozenset({0x13, 0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E, 0x91, *range(0x70, 0x88)})


@dataclass(frozen=True)
class Bind:
    button: int = 0
    key: int = 0
    mods: int = 0

    @staticmethod
    def mouse(button: int) -> Bind:
        return Bind(button=button)

    @staticmethod
    def keyboard(key: int, mods: int = 0) -> Bind:
        return Bind(key=key, mods=mods & MODS)


DEFAULTS: Mapping[str, Bind] = {MARK_SELF: Bind.mouse(4), PIN: Bind.mouse(5)}


def key_name(vk: int, char: str = "") -> str:
    if vk in _NAMES:
        return _NAMES[vk]
    if char.strip():
        return char.upper()
    return f"Touche {vk}"


def label(bind: Bind, char_of: Callable[[int], str] | None = None) -> str:
    if bind.button:
        return f"Souris {bind.button}"
    parts = [name for flag, name in ((MOD_CONTROL, "Ctrl"), (MOD_SHIFT, "Maj"), (MOD_ALT, "Alt")) if bind.mods & flag]
    parts.append(key_name(bind.key, char_of(bind.key) if char_of else ""))
    return "+".join(parts)


def problem(bind: Bind, taken: Mapping[Bind, str]) -> str | None:
    """Why this bind cannot be used, or None. `taken` maps binds in use to their name."""

    if bind.button:
        if bind.button not in MOUSE_BUTTONS:
            return "Seuls les boutons souris 3, 4 et 5 sont possibles."
    elif bind.key == VK_ESCAPE:
        return "Échap sert à annuler."
    elif bind.key in MODIFIER_KEYS or not 0 < bind.key < 0xFF:
        return "Touche non prise en charge."
    elif not bind.mods and bind.key not in FREE_KEYS:
        return "Ajoutez Ctrl, Maj ou Alt : cette touche sert à écrire."
    if bind in taken:
        return f"Déjà utilisée : {taken[bind]}."
    return None


def to_json(binds: Mapping[str, Bind]) -> dict:
    data = {}
    for action in ACTIONS:
        bind = binds[action]
        data[action] = {"button": bind.button} if bind.button else {"key": bind.key, "mods": bind.mods}
    return data


def from_json(data: object) -> dict[str, Bind]:
    """Saved binds; anything missing, invalid or clashing falls back to the defaults."""

    result = dict(DEFAULTS)
    if not isinstance(data, dict):
        return result
    for action in ACTIONS:
        entry = data.get(action)
        if not isinstance(entry, dict):
            continue
        try:
            if "button" in entry:
                bind = Bind.mouse(int(entry["button"]))
            else:
                bind = Bind.keyboard(int(entry["key"]), int(entry.get("mods", 0)))
        except (KeyError, TypeError, ValueError):
            continue
        if problem(bind, {}) is None:
            result[action] = bind
    if result[MARK_SELF] == result[PIN]:
        return dict(DEFAULTS)
    return result
