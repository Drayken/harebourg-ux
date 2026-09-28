"""HUD and map painting for the layered overlay. GDI+ writes premultiplied pixels."""

from __future__ import annotations

import ctypes
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum

from confusion import PHASES, Rotation, short_label
from grid import Cell, Kind, Layout, Projection

gdiplus = ctypes.WinDLL("gdiplus", use_last_error=True)

PixelFormat32bppPARGB = 0x000E200B
UnitPixel = 2
SmoothingModeNone = 3
SmoothingModeAntiAlias = 4
TextRenderingHintAntiAliasGridFit = 3
PixelOffsetModeNone = 3
PixelOffsetModeHalf = 4
FontStyleBold = 1
FontStyleRegular = 0
FlushIntentionSync = 1
StringAlignmentNear = 0
StringAlignmentCenter = 1
StringAlignmentFar = 2

_token: ctypes.c_ulong | None = None


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = (
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    )


class RectF(ctypes.Structure):
    _fields_ = (
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("width", ctypes.c_float),
        ("height", ctypes.c_float),
    )


class GUID(ctypes.Structure):
    _fields_ = (
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    )


def _status(code: int, action: str) -> None:
    if code != 0:
        raise RuntimeError(f"{action} a échoué ({code})")


def startup() -> None:
    global _token
    if _token is not None:
        return
    startup_input = GdiplusStartupInput(1, None, False, False)
    token = ctypes.c_ulong()
    gdiplus.GdiplusStartup.argtypes = [
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(GdiplusStartupInput),
        ctypes.c_void_p,
    ]
    gdiplus.GdiplusStartup.restype = ctypes.c_int
    _status(
        gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup_input), None),
        "GdiplusStartup",
    )
    _token = token


def shutdown() -> None:
    global _token
    if _token is None:
        return
    gdiplus.GdiplusShutdown.argtypes = [ctypes.c_ulong]
    gdiplus.GdiplusShutdown(_token)
    _token = None


def _gp(name: str, restype: type, *argtypes: type) -> None:
    fn = getattr(gdiplus, name)
    fn.restype = restype
    fn.argtypes = list(argtypes)


def bind() -> None:
    real = ctypes.c_float
    ptr = ctypes.c_void_p
    _gp("GdipCreateBitmapFromScan0", ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ptr))
    _gp("GdipGetImageGraphicsContext", ctypes.c_int, ptr, ctypes.POINTER(ptr))
    _gp("GdipDeleteGraphics", ctypes.c_int, ptr)
    _gp("GdipFlush", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipSetSmoothingMode", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipSetTextRenderingHint", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipSetPixelOffsetMode", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipCreateSolidFill", ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ptr))
    _gp("GdipDeleteBrush", ctypes.c_int, ptr)
    _gp("GdipFillRectangle", ctypes.c_int, ptr, ptr, real, real, real, real)
    _gp("GdipCreatePen1", ctypes.c_int, ctypes.c_uint32, real, ctypes.c_int, ctypes.POINTER(ptr))
    _gp("GdipDeletePen", ctypes.c_int, ptr)
    _gp("GdipSetPenStartCap", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipSetPenEndCap", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipDrawArc", ctypes.c_int, ptr, ptr, real, real, real, real, real, real)
    _gp("GdipDrawLine", ctypes.c_int, ptr, ptr, real, real, real, real)
    _gp("GdipFillPolygonI", ctypes.c_int, ptr, ptr, ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    _gp("GdipDrawPolygonI", ctypes.c_int, ptr, ptr, ctypes.c_void_p, ctypes.c_int)
    _gp("GdipSetPenLineJoin", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipCreatePath", ctypes.c_int, ctypes.c_int, ctypes.POINTER(ptr))
    _gp("GdipDeletePath", ctypes.c_int, ptr)
    _gp("GdipAddPathArc", ctypes.c_int, ptr, real, real, real, real, real, real)
    _gp("GdipAddPathPolygonI", ctypes.c_int, ptr, ctypes.c_void_p, ctypes.c_int)
    _gp("GdipAddPathLineI", ctypes.c_int, ptr, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
    _gp("GdipStartPathFigure", ctypes.c_int, ptr)
    _gp("GdipClosePathFigure", ctypes.c_int, ptr)
    _gp("GdipFillPath", ctypes.c_int, ptr, ptr, ptr)
    _gp("GdipDrawPath", ctypes.c_int, ptr, ptr, ptr)
    _gp("GdipCreateFontFamilyFromName", ctypes.c_int, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ptr))
    _gp("GdipDeleteFontFamily", ctypes.c_int, ptr)
    _gp("GdipCreateFont", ctypes.c_int, ptr, real, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ptr))
    _gp("GdipDeleteFont", ctypes.c_int, ptr)
    _gp("GdipCreateStringFormat", ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ptr))
    _gp("GdipDeleteStringFormat", ctypes.c_int, ptr)
    _gp("GdipSetStringFormatAlign", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipSetStringFormatLineAlign", ctypes.c_int, ptr, ctypes.c_int)
    _gp("GdipDrawString", ctypes.c_int, ptr, wintypes.LPCWSTR, ctypes.c_int, ptr, ctypes.POINTER(RectF), ptr, ptr)
    _gp(
        "GdipMeasureString",
        ctypes.c_int,
        ptr,
        wintypes.LPCWSTR,
        ctypes.c_int,
        ptr,
        ctypes.POINTER(RectF),
        ptr,
        ctypes.POINTER(RectF),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
    )
    _gp("GdipStringFormatGetGenericTypographic", ctypes.c_int, ctypes.POINTER(ptr))
    _gp("GdipCloneStringFormat", ctypes.c_int, ptr, ctypes.POINTER(ptr))
    _gp("GdipAddPathLine", ctypes.c_int, ptr, real, real, real, real)
    _gp("GdipFillEllipse", ctypes.c_int, ptr, ptr, real, real, real, real)
    _gp("GdipSaveImageToFile", ctypes.c_int, ptr, wintypes.LPCWSTR, ctypes.POINTER(GUID), ctypes.c_void_p)
    _gp("GdipDisposeImage", ctypes.c_int, ptr)


bind()


class PointI(ctypes.Structure):
    _fields_ = (("x", ctypes.c_int), ("y", ctypes.c_int))


@dataclass(frozen=True)
class MapMarks:
    """Cells to emphasize on top of the grid. Any of them may be off the map."""

    hover: Cell | None = None
    self_cell: Cell | None = None
    landing: Cell | None = None
    aim: Cell | None = None
    pin: Cell | None = None


class Level(Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    ACTIVE = "active"
    IDLE = "idle"


@dataclass(frozen=True)
class Status:
    level: Level
    text: str


@dataclass(frozen=True)
class Key:
    """A keycap in a hint line. Plain strings in the same line are captions."""

    label: str


HintLine = tuple[Key | str, ...]

HANDLE_DIP = 22
HUD_SHADOW_DIP = 6
_PANEL_W_DIP = 520
_HINTS_TOP_DIP = 192
_HINT_ROW_DIP = 26


def hud_dip(hint_lines: int) -> tuple[int, int]:
    """Bitmap size of the HUD, shadow included, for this many hint lines."""

    panel_h = _HINTS_TOP_DIP + _HINT_ROW_DIP * hint_lines + 6
    return _PANEL_W_DIP + 2 * HUD_SHADOW_DIP, panel_h + 2 * HUD_SHADOW_DIP


class Surface:
    """A top-down 32-bit bitmap the overlay can hand to UpdateLayeredWindow."""

    def __init__(self, width: int, height: int, pixels: int) -> None:
        startup()
        self.width = width
        self.height = height
        self._pixels = pixels
        self._bitmap = ctypes.c_void_p()
        stride = width * 4
        _status(
            gdiplus.GdipCreateBitmapFromScan0(
                width,
                height,
                stride,
                PixelFormat32bppPARGB,
                ctypes.c_void_p(pixels),
                ctypes.byref(self._bitmap),
            ),
            "GdipCreateBitmapFromScan0",
        )

    @contextmanager
    def _graphics(self) -> Iterator[ctypes.c_void_p]:
        graphics = ctypes.c_void_p()
        _status(
            gdiplus.GdipGetImageGraphicsContext(self._bitmap, ctypes.byref(graphics)),
            "GdipGetImageGraphicsContext",
        )
        try:
            yield graphics
            gdiplus.GdipFlush(graphics, FlushIntentionSync)
        finally:
            gdiplus.GdipDeleteGraphics(graphics)

    def draw_hud(
        self,
        scale: float,
        rotation: Rotation | None,
        statuses: Sequence[Status],
        hints: Sequence[HintLine],
    ) -> None:
        with self._graphics() as graphics:
            gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias)
            gdiplus.GdipSetTextRenderingHint(graphics, TextRenderingHintAntiAliasGridFit)
            gdiplus.GdipSetPixelOffsetMode(graphics, PixelOffsetModeHalf)
            _paint(graphics, self.width, self.height, scale, rotation, statuses, hints)

    def draw_map(
        self,
        layout: Layout,
        projection: Projection,
        marks: MapMarks,
        scale: float,
        setup: bool = False,
    ) -> None:
        """Paint the diamond grid. The caller clears the pixels first."""

        with self._graphics() as graphics:
            # 2:1 iso edges are crisp pixel stairs without antialiasing.
            gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeNone)
            gdiplus.GdipSetPixelOffsetMode(graphics, PixelOffsetModeNone)
            _paint_map(graphics, layout, projection, marks, scale, setup)

    def draw_chat_setup(self, region: tuple[int, int, int, int] | None, scale: float) -> None:
        """Dim the game and outline the combat-log rectangle being anchored."""

        with self._graphics() as graphics:
            gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeNone)
            gdiplus.GdipSetPixelOffsetMode(graphics, PixelOffsetModeNone)
            gdiplus.GdipSetTextRenderingHint(graphics, TextRenderingHintAntiAliasGridFit)
            _paint_chat_setup(graphics, self.width, self.height, region, scale)

    def save_png(self, path: str) -> None:
        encoder = _png_clsid()
        _status(
            gdiplus.GdipSaveImageToFile(self._bitmap, path, ctypes.byref(encoder), None),
            "GdipSaveImageToFile",
        )

    def dispose(self) -> None:
        if self._bitmap:
            gdiplus.GdipDisposeImage(self._bitmap)
            self._bitmap = ctypes.c_void_p()


def _png_clsid() -> GUID:
    value = uuid.UUID("557cf406-1a04-11d3-9a73-0000f81ef32e")
    data4 = (ctypes.c_ubyte * 8).from_buffer_copy(value.bytes[8:])
    return GUID(value.time_low, value.time_mid, value.time_hi_version, data4)


def _argb(alpha: int, red: int, green: int, blue: int) -> int:
    return (alpha << 24) | (red << 16) | (green << 8) | blue


def _fill(color: int) -> ctypes.c_void_p:
    brush = ctypes.c_void_p()
    _status(gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush)), "GdipCreateSolidFill")
    return brush


def _pen(color: int, width: float) -> ctypes.c_void_p:
    pen = ctypes.c_void_p()
    _status(gdiplus.GdipCreatePen1(color, width, UnitPixel, ctypes.byref(pen)), "GdipCreatePen1")
    return pen


def _rounded_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    top_only: bool = False,
) -> ctypes.c_void_p:
    path = ctypes.c_void_p()
    _status(gdiplus.GdipCreatePath(0, ctypes.byref(path)), "GdipCreatePath")
    diameter = radius * 2
    gdiplus.GdipAddPathArc(path, x, y, diameter, diameter, 180, 90)
    gdiplus.GdipAddPathArc(path, x + width - diameter, y, diameter, diameter, 270, 90)
    if top_only:
        gdiplus.GdipAddPathLine(path, x + width, y + height, x, y + height)
    else:
        gdiplus.GdipAddPathArc(path, x + width - diameter, y + height - diameter, diameter, diameter, 0, 90)
        gdiplus.GdipAddPathArc(path, x, y + height - diameter, diameter, diameter, 90, 90)
    gdiplus.GdipClosePathFigure(path)
    return path


def _box(
    graphics: ctypes.c_void_p,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    fill: int,
    border: int | None = None,
    border_width: float = 1.0,
    top_only: bool = False,
) -> None:
    path = _rounded_rect(x, y, width, height, radius, top_only)
    brush = _fill(fill)
    pen = _pen(border, border_width) if border is not None else None
    try:
        gdiplus.GdipFillPath(graphics, brush, path)
        if pen is not None:
            gdiplus.GdipDrawPath(graphics, pen, path)
    finally:
        gdiplus.GdipDeleteBrush(brush)
        if pen is not None:
            gdiplus.GdipDeletePen(pen)
        gdiplus.GdipDeletePath(path)


def _line(graphics: ctypes.c_void_p, color: int, width: float, x1: float, y1: float, x2: float, y2: float) -> None:
    pen = _pen(color, width)
    try:
        gdiplus.GdipDrawLine(graphics, pen, x1, y1, x2, y2)
    finally:
        gdiplus.GdipDeletePen(pen)


@contextmanager
def _typeface(family_name: str, size: float, style: int = 0) -> Iterator[ctypes.c_void_p]:
    family, font = _font(family_name, size, style)
    try:
        yield font
    finally:
        gdiplus.GdipDeleteFont(font)
        gdiplus.GdipDeleteFontFamily(family)


@contextmanager
def _brush(color: int) -> Iterator[ctypes.c_void_p]:
    brush = _fill(color)
    try:
        yield brush
    finally:
        gdiplus.GdipDeleteBrush(brush)


def _string_format(typographic: bool) -> ctypes.c_void_p:
    """A new format the caller deletes. Typographic drops GDI+'s side padding so
    measured widths and left edges line up."""

    string_format = ctypes.c_void_p()
    if typographic:
        shared = ctypes.c_void_p()
        _status(gdiplus.GdipStringFormatGetGenericTypographic(ctypes.byref(shared)), "GetGenericTypographic")
        _status(gdiplus.GdipCloneStringFormat(shared, ctypes.byref(string_format)), "GdipCloneStringFormat")
    else:
        _status(gdiplus.GdipCreateStringFormat(0, 0, ctypes.byref(string_format)), "GdipCreateStringFormat")
    return string_format


def _measure(graphics: ctypes.c_void_p, text: str, font: ctypes.c_void_p) -> float:
    string_format = _string_format(typographic=True)
    layout = RectF(0, 0, 10_000, 1_000)
    box = RectF()
    try:
        _status(
            gdiplus.GdipMeasureString(
                graphics, text, len(text), font, ctypes.byref(layout), string_format, ctypes.byref(box), None, None
            ),
            "GdipMeasureString",
        )
    finally:
        gdiplus.GdipDeleteStringFormat(string_format)
    return box.width


def _font(family_name: str, size: float, style: int) -> tuple[ctypes.c_void_p, ctypes.c_void_p]:
    family = ctypes.c_void_p()
    status = gdiplus.GdipCreateFontFamilyFromName(family_name, None, ctypes.byref(family))
    if status != 0:
        status = gdiplus.GdipCreateFontFamilyFromName("Arial", None, ctypes.byref(family))
        _status(status, "GdipCreateFontFamilyFromName")
    font = ctypes.c_void_p()
    _status(
        gdiplus.GdipCreateFont(family, size, style, UnitPixel, ctypes.byref(font)),
        "GdipCreateFont",
    )
    return family, font


def _draw_string(
    graphics: ctypes.c_void_p,
    text: str,
    font: ctypes.c_void_p,
    brush: ctypes.c_void_p,
    x: float,
    y: float,
    width: float,
    height: float,
    align: int = StringAlignmentNear,
    line_align: int | None = None,
    typographic: bool = False,
) -> None:
    layout = RectF(x, y, width, height)
    string_format = _string_format(typographic)
    try:
        gdiplus.GdipSetStringFormatAlign(string_format, align)
        gdiplus.GdipSetStringFormatLineAlign(string_format, align if line_align is None else line_align)
        gdiplus.GdipDrawString(
            graphics,
            text,
            len(text),
            font,
            ctypes.byref(layout),
            string_format,
            brush,
        )
    finally:
        gdiplus.GdipDeleteStringFormat(string_format)


def _paint(
    graphics: ctypes.c_void_p,
    width: int,
    height: int,
    scale: float,
    rotation: Rotation | None,
    statuses: Sequence[Status],
    hints: Sequence[HintLine],
) -> None:
    """A Dofus-style window: title bar, arrow slot, status rows, life bands, keycaps."""

    def px(value: float) -> float:
        return value * scale

    shadow = px(HUD_SHADOW_DIP)
    left, top = shadow, shadow
    panel_w, panel_h = width - 2 * shadow, height - 2 * shadow
    radius = px(6)
    hairline = max(1.0, scale)

    # The game is busy behind the HUD; a soft drop shadow keeps the edge readable.
    rings = 6
    for ring in range(rings, 0, -1):
        grow = shadow * ring / rings
        _box(
            graphics,
            left - grow,
            top - grow + px(2),
            panel_w + 2 * grow,
            panel_h + 2 * grow,
            radius + grow,
            _argb(14, 0, 0, 0),
        )
    _box(graphics, left, top, panel_w, panel_h, radius, _argb(246, *_PANEL))
    header_h = px(28)
    _box(graphics, left, top, panel_w, header_h, radius, _argb(255, *_HEADER), top_only=True)
    _line(graphics, _argb(255, *_BORDER), hairline, left, top + header_h, left + panel_w, top + header_h)
    _box(graphics, left, top, panel_w, panel_h, radius, 0, _argb(255, *_BORDER), hairline)

    with _typeface("Segoe UI Semibold", px(13)) as font, _brush(_argb(255, *_INK)) as ink:
        _draw_string(
            graphics, "Harebourg UX", font, ink, left, top, panel_w, header_h, StringAlignmentCenter
        )

    pad = px(14)
    inner_x = left + pad
    inner_w = panel_w - 2 * pad

    slot = px(64)
    slot_y = top + px(40)
    _box(graphics, inner_x, slot_y, slot, slot, px(4), _argb(255, *_SLOT), _argb(255, *_SLOT_BORDER), hairline)
    _draw_icon(graphics, inner_x + slot / 2, slot_y + slot / 2, px(21), rotation, scale)

    text_x = inner_x + slot + px(14)
    text_w = left + panel_w - pad - text_x
    title = "En attente" if rotation is None else rotation.label
    title_color = _INK_3 if rotation is None else _INK
    with _typeface("Segoe UI", px(22), FontStyleBold) as font, _brush(_argb(255, *title_color)) as ink:
        _draw_string(graphics, title, font, ink, text_x, top + px(37), text_w, px(32), typographic=True)

    row_h = px(19)
    dot = px(7)
    with _typeface("Segoe UI", px(13)) as font, _brush(_argb(255, *_INK_2)) as ink:
        for index, status in enumerate(statuses):
            row_y = top + px(72) + index * row_h
            with _brush(_argb(255, *_LEVEL_COLORS[status.level])) as dot_ink:
                gdiplus.GdipFillEllipse(graphics, dot_ink, text_x, row_y + (row_h - dot) / 2, dot, dot)
            _draw_string(
                graphics,
                status.text,
                font,
                ink,
                text_x + dot + px(7),
                row_y,
                text_w - dot - px(7),
                row_h,
                StringAlignmentNear,
                StringAlignmentCenter,
                typographic=True,
            )

    label_y = top + px(118)
    _section_label(graphics, "Départ de tour selon votre vie", inner_x, label_y, inner_w, px(14), scale)
    _draw_phases(graphics, inner_x, label_y + px(18), inner_w, px(18), scale)

    rule_y = top + px(182)
    _line(graphics, _argb(255, *_BORDER), hairline, inner_x, rule_y, inner_x + inner_w, rule_y)
    for index, hint in enumerate(hints):
        _draw_hint_line(graphics, hint, inner_x, top + px(_HINTS_TOP_DIP + index * _HINT_ROW_DIP), scale)


_PANEL = (33, 38, 51)
_HEADER = (45, 52, 70)
_BORDER = (72, 81, 104)
_SLOT = (21, 25, 34)
_SLOT_BORDER = (62, 70, 90)
_INK = (240, 242, 246)
_INK_2 = (178, 185, 200)
_INK_3 = (124, 132, 150)
_KEY = (55, 62, 82)
_KEY_BORDER = (90, 100, 124)
_KEY_SHADE = (16, 19, 26)

_LEVEL_COLORS = {
    Level.OK: (160, 204, 64),
    Level.WARN: (236, 168, 56),
    Level.ERROR: (226, 86, 74),
    Level.ACTIVE: (92, 170, 238),
    Level.IDLE: (124, 132, 150),
}

_PHASE_COLORS = {
    Rotation.STRAIGHT: (160, 168, 184),
    Rotation.CLOCKWISE: (238, 182, 60),
    Rotation.HALF: (220, 98, 86),
    Rotation.COUNTERCLOCKWISE: (92, 164, 228),
}


def _section_label(
    graphics: ctypes.c_void_p,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    scale: float,
) -> None:
    """Small caps label with a rule running to the right edge."""

    text = text.upper()
    with _typeface("Segoe UI Semibold", 10.5 * scale) as font, _brush(_argb(255, *_INK_3)) as ink:
        text_w = _measure(graphics, text, font)
        _draw_string(
            graphics, text, font, ink, x, y, text_w + scale * 2, height, StringAlignmentNear, StringAlignmentCenter,
            typographic=True,
        )
    rule_x = x + text_w + 8 * scale
    if rule_x < x + width:
        mid = round(y + height / 2)
        _line(graphics, _argb(255, *_BORDER), max(1.0, scale), rule_x, mid, x + width, mid)


def _draw_phases(
    graphics: ctypes.c_void_p,
    x: float,
    y: float,
    width: float,
    height: float,
    scale: float,
) -> None:
    """The player's life bar, full on the left, split into turn-start redirect bands."""

    def at(percent: int) -> float:
        return x + width * (100 - percent) / 100

    gap = max(1.0, 2 * scale)
    range_h = 14 * scale
    range_y = y + height + 2 * scale
    with (
        _typeface("Segoe UI", 10.5 * scale, FontStyleBold) as label_font,
        _typeface("Segoe UI", 10 * scale) as range_font,
        _brush(_argb(255, 18, 20, 26)) as ink,
        _brush(_argb(255, *_INK_3)) as range_ink,
    ):
        high = 100
        for low, rotation in PHASES:
            band_left, band_right = at(high), at(low)
            band_w = band_right - band_left - gap
            _box(graphics, band_left + gap / 2, y, band_w, height, 2 * scale, _argb(235, *_PHASE_COLORS[rotation]))
            _draw_string(
                graphics, short_label(rotation), label_font, ink, band_left, y, band_right - band_left, height,
                StringAlignmentCenter,
            )
            # Bands are inclusive at both ends.
            top = high if high == 100 else high - 1
            _draw_string(
                graphics, f"{top}\u2013{low} %", range_font, range_ink, band_left, range_y, band_right - band_left,
                range_h, StringAlignmentCenter, StringAlignmentNear,
            )
            high = low


def _draw_hint_line(graphics: ctypes.c_void_p, items: HintLine, x: float, y: float, scale: float) -> None:
    key_h = 20 * scale
    key_pad = 6 * scale
    with (
        _typeface("Segoe UI Semibold", 11.5 * scale) as key_font,
        _typeface("Segoe UI", 12 * scale) as caption_font,
        _brush(_argb(255, *_INK)) as key_ink,
        _brush(_argb(255, *_INK_2)) as caption_ink,
    ):
        cursor = x
        for item in items:
            if isinstance(item, Key):
                key_w = max(key_h, _measure(graphics, item.label, key_font) + 2 * key_pad)
                _box(graphics, cursor, y + 2 * scale, key_w, key_h, 3 * scale, _argb(255, *_KEY_SHADE))
                _box(graphics, cursor, y, key_w, key_h, 3 * scale, _argb(255, *_KEY), _argb(255, *_KEY_BORDER))
                _draw_string(
                    graphics, item.label, key_font, key_ink, cursor, y, key_w, key_h,
                    StringAlignmentCenter, StringAlignmentCenter,
                )
                cursor += key_w + 5 * scale
            else:
                caption_w = _measure(graphics, item, caption_font)
                _draw_string(
                    graphics, item, caption_font, caption_ink, cursor, y, caption_w + 2 * scale, key_h,
                    StringAlignmentNear, StringAlignmentCenter, typographic=True,
                )
                cursor += caption_w + (5 if item == "+" else 14) * scale


# Unit marks. +y is down. The tail is the aim, the head is where the spell lands.
_ARROW_UP = (
    (0.00, -1.00),
    (0.50, -0.22),
    (0.22, -0.22),
    (0.22, 1.00),
    (-0.22, 1.00),
    (-0.22, -0.22),
    (-0.50, -0.22),
)
_BEND_RIGHT = (
    (-0.78, 1.00),
    (-0.34, 1.00),
    (-0.34, -0.02),
    (0.18, -0.02),
    (0.18, 0.30),
    (1.00, -0.28),
    (0.18, -0.86),
    (0.18, -0.54),
    (-0.78, -0.54),
)


def _draw_icon(
    graphics: ctypes.c_void_p,
    cx: float,
    cy: float,
    size: float,
    rotation: Rotation | None,
    scale: float,
) -> None:
    outline = _argb(255, *_SLOT)
    if rotation is None:
        _polygon(
            graphics,
            _place(((-0.46, -0.1), (0.46, -0.1), (0.46, 0.1), (-0.46, 0.1)), cx, cy, size),
            _argb(255, *_INK_3),
            outline,
            scale,
        )
        return
    if rotation is Rotation.STRAIGHT:
        shape = _ARROW_UP
    elif rotation is Rotation.HALF:
        shape = tuple((x, -y) for x, y in _ARROW_UP)
    elif rotation is Rotation.COUNTERCLOCKWISE:
        shape = _BEND_RIGHT
    else:
        # Horaire lands clockwise from the click on screen, so its arrow bends left.
        shape = tuple((-x, y) for x, y in _BEND_RIGHT)
    _polygon(
        graphics,
        _place(shape, cx, cy, size),
        _argb(255, *_PHASE_COLORS[rotation]),
        outline,
        scale,
    )


def _place(
    shape: tuple[tuple[float, float], ...],
    cx: float,
    cy: float,
    size: float,
) -> list[tuple[float, float]]:
    return [(cx + x * size, cy + y * size) for x, y in shape]


def _polygon(
    graphics: ctypes.c_void_p,
    points: list[tuple[float, float]],
    fill: int,
    outline: int,
    scale: float,
) -> None:
    count = len(points)
    packed = (PointI * count)(*(PointI(round(x), round(y)) for x, y in points))
    pointer = ctypes.cast(packed, ctypes.c_void_p)
    pen = _pen(outline, max(2.0, 2.6 * scale))
    brush = _fill(fill)
    try:
        gdiplus.GdipSetPenLineJoin(pen, 2)
        gdiplus.GdipDrawPolygonI(graphics, pen, pointer, count)
        gdiplus.GdipFillPolygonI(graphics, brush, pointer, count, 0)
    finally:
        gdiplus.GdipDeletePen(pen)
        gdiplus.GdipDeleteBrush(brush)


# Floor, wall, and mark colors follow the comteharebourg.com simulator so the
# two read the same. Alpha is ours: the game has to show through.
_FLOOR_LIGHT = (149, 141, 105)
_FLOOR_DARK = (139, 133, 97)
_WALL = (78, 74, 54)
_EDGE = (240, 232, 200)
_HOLE = (214, 72, 56)
_SELF = (30, 0, 197)
_AIM = (175, 0, 0)
_LANDING = (0, 116, 58)
_FAIL = (12, 8, 8)
_HOVER = (255, 255, 255)


@dataclass(frozen=True)
class _MapStyle:
    floor_alpha: int
    edge_alpha: int
    wall_alpha: int


_PLAY = _MapStyle(floor_alpha=0, edge_alpha=70, wall_alpha=120)
_SETUP_RED = (255, 40, 40)


def _paint_map(
    graphics: ctypes.c_void_p,
    layout: Layout,
    projection: Projection,
    marks: MapMarks,
    scale: float,
    setup: bool,
) -> None:
    style = _PLAY
    light: list[Cell] = []
    dark: list[Cell] = []
    walls: list[Cell] = []
    holes: list[Cell] = []
    for cell, kind in layout.cells():
        if kind is Kind.WALKABLE:
            (light if (cell[0] + cell[1]) % 2 == 0 else dark).append(cell)
        elif kind is Kind.WALL:
            walls.append(cell)
        elif layout.is_hole(cell):
            holes.append(cell)

    if setup:
        used = light + dark + walls
        _fill_cells(graphics, projection, used, _argb(96, *_SETUP_RED))
        _outline_cells(
            graphics,
            projection,
            used,
            _argb(255, *_SETUP_RED),
            max(2, round(2 * scale)),
        )
        _cross_cells(graphics, projection, holes, _argb(255, 255, 228, 228), max(2, round(2 * scale)))
        _draw_handles(graphics, layout, projection, scale)
        return

    if style.floor_alpha:
        _fill_cells(graphics, projection, light, _argb(style.floor_alpha, *_FLOOR_LIGHT))
        _fill_cells(graphics, projection, dark, _argb(style.floor_alpha, *_FLOOR_DARK))
    _fill_cells(graphics, projection, walls, _argb(style.wall_alpha, *_WALL))
    _outline_cells(graphics, projection, light + dark + walls, _argb(style.edge_alpha, *_EDGE), 1)

    if marks.aim is not None:
        _fill_cells(graphics, projection, [marks.aim], _argb(190, *_AIM))
    if marks.landing is not None:
        if layout.walkable(marks.landing):
            _fill_cells(graphics, projection, [marks.landing], _argb(210, *_LANDING))
        else:
            _fill_cells(graphics, projection, [marks.landing], _argb(220, *_FAIL))
            _cross_cells(graphics, projection, [marks.landing], _argb(255, *_HOLE), max(2, round(3 * scale)))
    if marks.self_cell is not None:
        _fill_cells(graphics, projection, [marks.self_cell], _argb(210, *_SELF))
    if marks.pin is not None:
        _outline_cells(graphics, projection, [marks.pin], _argb(240, 60, 220, 130), max(2, round(2 * scale)))
    if marks.hover is not None:
        _outline_cells(graphics, projection, [marks.hover], _argb(235, *_HOVER), max(2, round(2 * scale)))
    _label_marks(graphics, projection, marks)


_CHAT = (242, 184, 62)


def _paint_chat_setup(
    graphics: ctypes.c_void_p,
    width: int,
    height: int,
    region: tuple[int, int, int, int] | None,
    scale: float,
) -> None:
    # Fully transparent pixels would let clicks fall through to the game.
    dim = _fill(_argb(90, 0, 0, 0))
    try:
        gdiplus.GdipFillRectangle(graphics, dim, 0, 0, width, height)
    finally:
        gdiplus.GdipDeleteBrush(dim)
    if region is None:
        return
    x, y, region_width, region_height = region
    fill = _fill(_argb(60, *_CHAT))
    pen = _pen(_argb(255, *_CHAT), max(2, round(2 * scale)))
    ink = _fill(_argb(255, *_INK))
    family, font = _font("Segoe UI Semibold", 13 * scale, FontStyleRegular)
    try:
        gdiplus.GdipFillRectangle(graphics, fill, x, y, region_width, region_height)
        points = (PointI * 4)(
            PointI(x, y),
            PointI(x + region_width - 1, y),
            PointI(x + region_width - 1, y + region_height - 1),
            PointI(x, y + region_height - 1),
        )
        gdiplus.GdipDrawPolygonI(graphics, pen, ctypes.cast(points, ctypes.c_void_p), 4)
        text = "Chat de combat"
        label_h = 24 * scale
        label_w = _measure(graphics, text, font) + 20 * scale
        gap = 6 * scale
        label_y = y - label_h - gap if y >= label_h + gap else y + region_height + gap
        gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias)
        _box(graphics, x, label_y, label_w, label_h, 4 * scale, _argb(250, *_HEADER), _argb(255, *_CHAT), scale)
        _draw_string(
            graphics, text, font, ink, x, label_y, label_w, label_h, StringAlignmentCenter, StringAlignmentCenter
        )
    finally:
        gdiplus.GdipDeleteBrush(fill)
        gdiplus.GdipDeletePen(pen)
        gdiplus.GdipDeleteBrush(ink)
        gdiplus.GdipDeleteFont(font)
        gdiplus.GdipDeleteFontFamily(family)


def _label_marks(graphics: ctypes.c_void_p, projection: Projection, marks: MapMarks) -> None:
    """Name the marked cells. MB4 is Moi, the pin is Cible, the aim cell is Vise."""

    grouped: dict[Cell, list[str]] = {}
    for cell, text in (
        (marks.self_cell, "Moi"),
        (marks.pin, "Cible"),
        (marks.aim, "Vise"),
    ):
        if cell is None:
            continue
        grouped.setdefault(cell, []).append(text)
    if not grouped:
        return

    # Diamond lines stay aliased. Labels need their own hint or they stair-step.
    gdiplus.GdipSetTextRenderingHint(graphics, TextRenderingHintAntiAliasGridFit)
    lines = max(len(texts) for texts in grouped.values())
    # "Cible" is the long one. Size from the diamond so it stays inside the middle band.
    em = max(8.0, min(projection.cell_height * 0.78 / lines, projection.cell_width * 0.20))
    family, font = _font("Segoe UI", em, FontStyleBold)
    ink = _fill(_argb(255, 255, 255, 255))
    shade = _fill(_argb(230, 8, 8, 10))
    try:
        box_w = projection.cell_width
        line_h = projection.cell_height * 0.86 / lines
        halo = max(1, round(em * 0.08))
        for cell, texts in grouped.items():
            cx, cy = projection.center(cell)
            block_h = line_h * len(texts)
            top = cy - block_h / 2
            left = cx - box_w / 2
            for index, text in enumerate(texts):
                y = top + index * line_h
                for dx in range(-halo, halo + 1):
                    for dy in range(-halo, halo + 1):
                        if dx == 0 and dy == 0:
                            continue
                        _draw_string(
                            graphics, text, font, shade, left + dx, y + dy, box_w, line_h, StringAlignmentCenter
                        )
                _draw_string(graphics, text, font, ink, left, y, box_w, line_h, StringAlignmentCenter)
    finally:
        gdiplus.GdipDeleteFont(font)
        gdiplus.GdipDeleteFontFamily(family)
        gdiplus.GdipDeleteBrush(ink)
        gdiplus.GdipDeleteBrush(shade)


def _draw_handles(graphics: ctypes.c_void_p, layout: Layout, projection: Projection, scale: float) -> None:
    bounds = projection.bounds(layout)
    if bounds is None:
        return
    left, top, right, bottom = bounds
    size = max(16, round(HANDLE_DIP * scale))
    half = size // 2
    brush = _fill(_argb(255, 255, 255, 255))
    pen = _pen(_argb(255, 12, 12, 12), max(2.0, 2 * scale))
    try:
        for cx, cy in ((left, top), (right, top), (left, bottom), (right, bottom)):
            x = cx - half
            y = cy - half
            gdiplus.GdipFillRectangle(graphics, brush, x, y, size, size)
            points = (PointI * 4)(
                PointI(x, y),
                PointI(x + size - 1, y),
                PointI(x + size - 1, y + size - 1),
                PointI(x, y + size - 1),
            )
            gdiplus.GdipDrawPolygonI(graphics, pen, ctypes.cast(points, ctypes.c_void_p), 4)
    finally:
        gdiplus.GdipDeleteBrush(brush)
        gdiplus.GdipDeletePen(pen)


def _diamond_path(projection: Projection, cells: list[Cell]) -> ctypes.c_void_p:
    path = ctypes.c_void_p()
    _status(gdiplus.GdipCreatePath(0, ctypes.byref(path)), "GdipCreatePath")
    for cell in cells:
        points = (PointI * 4)(*(PointI(x, y) for x, y in projection.diamond(cell)))
        gdiplus.GdipAddPathPolygonI(path, ctypes.cast(points, ctypes.c_void_p), 4)
    return path


def _fill_cells(graphics: ctypes.c_void_p, projection: Projection, cells: list[Cell], color: int) -> None:
    if not cells:
        return
    path = _diamond_path(projection, cells)
    brush = _fill(color)
    try:
        gdiplus.GdipFillPath(graphics, brush, path)
    finally:
        gdiplus.GdipDeleteBrush(brush)
        gdiplus.GdipDeletePath(path)


def _outline_cells(
    graphics: ctypes.c_void_p,
    projection: Projection,
    cells: list[Cell],
    color: int,
    width: int,
) -> None:
    # One path per call: GDI+ strokes it as a single shape, so an edge shared
    # by two cells is not blended twice and every line keeps the same alpha.
    if not cells:
        return
    path = _diamond_path(projection, cells)
    pen = _pen(color, width)
    try:
        gdiplus.GdipDrawPath(graphics, pen, path)
    finally:
        gdiplus.GdipDeletePen(pen)
        gdiplus.GdipDeletePath(path)


def _cross_cells(
    graphics: ctypes.c_void_p,
    projection: Projection,
    cells: list[Cell],
    color: int,
    width: int,
) -> None:
    if not cells:
        return
    path = ctypes.c_void_p()
    _status(gdiplus.GdipCreatePath(0, ctypes.byref(path)), "GdipCreatePath")
    pen = _pen(color, width)
    try:
        for cell in cells:
            # The diamond's own diagonals, inset from the corners. Upright
            # strokes never read as grid lines, which all run at 2:1.
            top, right, bottom, left = projection.diamond(cell)
            inset_x = (right[0] - left[0]) // 5
            inset_y = (bottom[1] - top[1]) // 5
            gdiplus.GdipStartPathFigure(path)
            gdiplus.GdipAddPathLineI(path, left[0] + inset_x, left[1], right[0] - inset_x, right[1])
            gdiplus.GdipStartPathFigure(path)
            gdiplus.GdipAddPathLineI(path, top[0], top[1] + inset_y, bottom[0], bottom[1] - inset_y)
        gdiplus.GdipDrawPath(graphics, pen, path)
    finally:
        gdiplus.GdipDeletePen(pen)
        gdiplus.GdipDeletePath(path)
