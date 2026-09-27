"""Map alignment profiles, the chat anchor and key binds, kept under %AppData%\\HarebourgUx\\.

A profile belongs to one map at one Dofus client size, relative to that
client area. A different client size never reuses it. The chat rectangle
follows the same rule.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import binds
from grid import Projection

SETTINGS_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "HarebourgUx"
PROFILES_PATH = SETTINGS_DIR / "profiles.json"
CHAT_PATH = SETTINGS_DIR / "chat.json"
BINDS_PATH = SETTINGS_DIR / "binds.json"
LAST_OCR_PATH = SETTINGS_DIR / "last-ocr.txt"

ChatRegion = tuple[int, int, int, int]


def _key(map_name: str, width: int, height: int) -> str:
    return f"{map_name}@{width}x{height}"


def load(path: Path = PROFILES_PATH) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    profiles = data.get("profiles") if isinstance(data, dict) else None
    return profiles if isinstance(profiles, dict) else {}


def find(map_name: str, width: int, height: int, path: Path = PROFILES_PATH) -> Projection | None:
    return _projection(load(path).get(_key(map_name, width, height)))


def cell_size_hint(width: int, height: int, path: Path = PROFILES_PATH) -> tuple[float, float] | None:
    """Cell size from any map aligned at this client size. Only the origin differs per map."""

    for entry in load(path).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("client_width") != width or entry.get("client_height") != height:
            continue
        projection = _projection(entry)
        if projection is not None:
            return projection.cell_width, projection.cell_height
    return None


def save(
    map_name: str,
    width: int,
    height: int,
    projection: Projection,
    path: Path = PROFILES_PATH,
) -> None:
    profiles = load(path)
    profiles[_key(map_name, width, height)] = {
        "map": map_name,
        "client_width": width,
        "client_height": height,
        "origin_x": round(projection.origin_x, 3),
        "origin_y": round(projection.origin_y, 3),
        "cell_width": round(projection.cell_width, 3),
        "cell_height": round(projection.cell_height, 3),
    }
    _write_json(path, {"profiles": profiles})


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _load_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def find_chat(width: int, height: int, path: Path = CHAT_PATH) -> ChatRegion | None:
    """The combat-log rectangle, relative to a client area of this size."""

    regions = _load_object(path).get("regions")
    entry = regions.get(f"{width}x{height}") if isinstance(regions, dict) else None
    if not isinstance(entry, dict):
        return None
    try:
        region = tuple(int(entry[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError):
        return None
    x, y, region_width, region_height = region
    if region_width <= 0 or region_height <= 0 or x < 0 or y < 0:
        return None
    if x + region_width > width or y + region_height > height:
        return None
    return x, y, region_width, region_height


def save_chat(width: int, height: int, region: ChatRegion, path: Path = CHAT_PATH) -> None:
    data = _load_object(path)
    regions = data.get("regions")
    if not isinstance(regions, dict):
        regions = {}
    x, y, region_width, region_height = region
    regions[f"{width}x{height}"] = {"x": x, "y": y, "width": region_width, "height": region_height}
    data["regions"] = regions
    _write_json(path, data)


def find_binds(path: Path = BINDS_PATH) -> dict[str, binds.Bind]:
    return binds.from_json(_load_object(path))


def save_binds(current: dict[str, binds.Bind], path: Path = BINDS_PATH) -> None:
    _write_json(path, binds.to_json(current))


def _projection(entry: object) -> Projection | None:
    if not isinstance(entry, dict):
        return None
    try:
        projection = Projection(
            float(entry["origin_x"]),
            float(entry["origin_y"]),
            float(entry["cell_width"]),
            float(entry["cell_height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if projection.cell_width <= 0 or projection.cell_height <= 0:
        return None
    return projection
