"""Click-through topmost windows. This is the only module that calls user32."""

from __future__ import annotations

import ctypes
import math
import os
from ctypes import wintypes

import binds
import chat
import ocr
import profiles
from binds import Bind
from confusion import Rotation, aim_cell, landing_cell
from draw import (
    HANDLE_DIP,
    HUD_SHADOW_DIP,
    HintLine,
    Key,
    Level,
    MapMarks,
    Status,
    Surface,
    hud_dip,
    shutdown,
    startup,
)
from grid import Cell, Projection, load_map

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20

SW_HIDE = 0
SW_SHOWNA = 8
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_NULL = 0x0000
WM_SETICON = 0x0080
WM_COMMAND = 0x0111
WM_CONTEXTMENU = 0x007B
WM_TIMER = 0x0113
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
MA_ACTIVATE = 1
MA_NOACTIVATE = 3
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_CAPTURECHANGED = 0x0215
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209
WM_HOTKEY = 0x0312
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D
WM_DPICHANGED = 0x02E0
WM_TRAY = 0x8001
WM_SIDE_BUTTON = 0x8002
WM_OCR = 0x8003
WM_BIND_MOUSE = 0x8004
WM_BIND_KEY = 0x8005

NIM_ADD = 0
NIM_DELETE = 2
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_SHOWTIP = 0x00000080
MF_STRING = 0x00000000
TPM_RIGHTALIGN = 0x0008
TPM_BOTTOMALIGN = 0x0020
TPM_RETURNCMD = 0x0100
ICON_SMALL = 0
ICON_BIG = 1
CMD_QUIT = 1
CMD_SETUP = 2
CMD_CHAT = 3
CMD_HIDE = 4
CMD_BIND_MARK = 5
CMD_BIND_PIN = 6
CMD_BIND_RESET = 7
MF_GRAYED = 0x00000001
MF_CHECKED = 0x00000008
MF_SEPARATOR = 0x00000800
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

MOD_SHIFT = binds.MOD_SHIFT
MOD_NOREPEAT = 0x4000
HOTKEY_MODS = MOD_SHIFT | MOD_NOREPEAT

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_DELETE = 0x2E
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
MAPVK_VK_TO_CHAR = 2
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

IDC_ARROW = 32512
IDC_CROSS = 32515
IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643
IDC_SIZEALL = 32646

ID_STRAIGHT = 1
ID_CLOCKWISE = 2
ID_HALF = 3
ID_COUNTER = 4
ID_BUMP = 5
ID_MARK_SELF = 6
ID_PIN = 7
ID_CLEAR_PIN = 8

HOTKEYS = (
    (ID_STRAIGHT, VK_UP, "Maj+Haut"),
    (ID_CLOCKWISE, VK_RIGHT, "Maj+Droite"),
    (ID_HALF, VK_DOWN, "Maj+Bas"),
    (ID_COUNTER, VK_LEFT, "Maj+Gauche"),
    (ID_BUMP, VK_SPACE, "Maj+Espace"),
    (ID_CLEAR_PIN, VK_DELETE, "Maj+Suppr"),
)
ACTION_IDS = {binds.MARK_SELF: ID_MARK_SELF, binds.PIN: ID_PIN}
BIND_COMMANDS = {CMD_BIND_MARK: binds.MARK_SELF, CMD_BIND_PIN: binds.PIN}

TIMER_FOLLOW = 1
TIMER_CURSOR = 2
TIMER_CHAT = 3
CURSOR_MS = 30
CHAT_MS = 250
# Dofus chat text is small; Windows OCR drops "90°" at that size and reads it at 2x.
CAPTURE_SCALE = 2
MIN_CHAT_PX = 24
SRCCOPY = 0x00CC0020
HALFTONE = 4

MAP_NAME = "comte"
DEFAULT_CELL = (86.0, 43.0)
MIN_CELL_WIDTH = 8.0
FIT_MARGIN_DIP = 48

HINT_DIRECTIONS: HintLine = (
    Key("Maj"), "+", Key("↑"), "droit", Key("→"), "horaire", Key("↓"), "180°", Key("←"), "contre",
    Key("Espace"), "mêlée",
)
HINT_SETUP: tuple[HintLine, ...] = (
    ("Glisser la grille, ou un coin pour la taille", Key("Échap"), "terminer"),
)
HINT_CHAT: tuple[HintLine, ...] = (
    ("Glisser un cadre sur le chat de combat", Key("Échap"), "terminer"),
)

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
BI_RGB = 0
DIB_RGB_COLORS = 0

MARGIN_DIP = 16 - HUD_SHADOW_DIP
CLASS_NAME = "HarebourgUxOverlay"
MAP_CLASS_NAME = "HarebourgUxMap"
FOLLOW_MS = 80

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class SIZE(ctypes.Structure):
    _fields_ = (("cx", wintypes.LONG), ("cy", wintypes.LONG))


class RECT(ctypes.Structure):
    _fields_ = (
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    )


class MSG(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    )


class GUID(ctypes.Structure):
    _fields_ = (
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    )


class ICONINFO(ctypes.Structure):
    _fields_ = (
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    )


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    )


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = (
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    )


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = (
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    )


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    )


def _bind() -> None:
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
    user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
    user32.CreateIconIndirect.restype = wintypes.HICON
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DestroyIcon.restype = wintypes.BOOL
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
    ]
    user32.TrackPopupMenu.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    gdi32.CreateBitmap.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    gdi32.CreateBitmap.restype = wintypes.HBITMAP
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(POINT),
        ctypes.POINTER(SIZE),
        wintypes.HDC,
        ctypes.POINTER(POINT),
        wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION),
        wintypes.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
    user32.LoadCursorW.restype = wintypes.HCURSOR
    user32.SetCursor.argtypes = [wintypes.HCURSOR]
    user32.SetCursor.restype = wintypes.HCURSOR
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.SetCapture.restype = wintypes.HWND
    user32.GetCapture.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE
    user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.SetStretchBltMode.restype = ctypes.c_int
    gdi32.SetBrushOrgEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    gdi32.SetBrushOrgEx.restype = wintypes.BOOL
    gdi32.StretchBlt.argtypes = [
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.DWORD,
    ]
    gdi32.StretchBlt.restype = wintypes.BOOL


_bind()


def enable_dpi_awareness() -> None:
    # Per-monitor v2 has to be set before any window exists, or Windows stretches
    # the overlay and the HUD goes soft.
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


def _last_error(action: str) -> RuntimeError:
    code = ctypes.get_last_error()
    return RuntimeError(f"{action} a échoué ({code})")


class Hud:
    def __init__(self) -> None:
        self.rotation: Rotation | None = None

    def set_rotation(self, rotation: Rotation) -> None:
        self.rotation = rotation

    def bump(self) -> None:
        if self.rotation is None:
            return
        self.rotation = self.rotation.bumped()


class Layer:
    """The bitmap behind one layered window."""

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self.width = 0
        self.height = 0
        self._mem_dc = wintypes.HDC(0)
        self._dib = wintypes.HBITMAP(0)
        self._pixels = 0
        self._surface: Surface | None = None

    def begin(self, width: int, height: int) -> Surface:
        """A cleared surface of this size, ready to paint and present."""

        if self._surface is None or (width, height) != (self.width, self.height):
            self._allocate(width, height)
        assert self._surface is not None
        ctypes.memset(self._pixels, 0, width * height * 4)
        return self._surface

    def _allocate(self, width: int, height: int) -> None:
        self.release()
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        self._mem_dc = gdi32.CreateCompatibleDC(None)
        self._dib = gdi32.CreateDIBSection(
            self._mem_dc, ctypes.byref(header), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not self._dib or not bits.value:
            raise _last_error("CreateDIBSection")
        self._pixels = bits.value
        self.width = width
        self.height = height
        self._surface = Surface(width, height, self._pixels)

    def present(self) -> None:
        if not self._mem_dc or not self._dib:
            return
        selected = gdi32.SelectObject(self._mem_dc, self._dib)
        origin = POINT(0, 0)
        size = SIZE(self.width, self.height)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(
            self.hwnd,
            None,
            None,
            ctypes.byref(size),
            self._mem_dc,
            ctypes.byref(origin),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        gdi32.SelectObject(self._mem_dc, selected)
        if not ok:
            raise _last_error("UpdateLayeredWindow")

    def release(self) -> None:
        if self._surface is not None:
            self._surface.dispose()
            self._surface = None
        if self._dib:
            gdi32.DeleteObject(self._dib)
            self._dib = wintypes.HBITMAP(0)
        if self._mem_dc:
            gdi32.DeleteDC(self._mem_dc)
            self._mem_dc = wintypes.HDC(0)
        self._pixels = 0


Drag = tuple[str, int, int, Projection, tuple[float, float]]


class Overlay:
    def __init__(self) -> None:
        startup()
        self.hud = Hud()
        self.layout = load_map(MAP_NAME)
        self.projection: Projection | None = None
        self.setup = False
        self.hidden = False
        self.self_cell: Cell | None = None
        self.pin_cell: Cell | None = None
        self.hover: Cell | None = None
        self._proc = WNDPROC(self._wnd_proc)
        self._map_proc = WNDPROC(self._map_wnd_proc)
        self._client: tuple[int, int, int, int] | None = None
        self._dofus = 0
        self._setup_backup: Projection | None = None
        self._drag: Drag | None = None
        self._scale = 1.0
        self._visible = False
        self._map_visible = False
        self._smoke_ticks = 0
        self._tray_added = False
        self._icon = _arrow_icon()
        self._mouse_hook = wintypes.HANDLE(0)
        self._mouse_proc = HOOKPROC(self._on_mouse)
        self._key_hook = wintypes.HANDLE(0)
        self._key_proc = HOOKPROC(self._on_capture_key)
        self.binds = profiles.find_binds()
        self.rebinding: str | None = None
        self._bind_error: str | None = None
        self._nid = NOTIFYICONDATAW()
        self.chat_setup = False
        self.chat_region: profiles.ChatRegion | None = None
        self._chat_backup: profiles.ChatRegion | None = None
        self._chat_drag: tuple[int, int] | None = None
        self._chat_frame: bytes | None = None
        self._watch = chat.Watch()
        self._chat_speaker: str | None = None
        self._reader: ocr.Reader | None = None
        self._register(CLASS_NAME, self._proc)
        self._register(MAP_CLASS_NAME, self._map_proc)
        # The map window is created first so the HUD stays above it.
        self.map_hwnd = self._create(MAP_CLASS_NAME, WS_EX_TOOLWINDOW)
        self.hwnd = self._create(CLASS_NAME, WS_EX_TOOLWINDOW)
        user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, self._icon)
        user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, self._icon)
        self._hud_layer = Layer(self.hwnd)
        self._map_layer = Layer(self.map_hwnd)
        self._add_tray()
        self._register_hotkeys()
        self._register_binds()
        self._install_side_buttons()
        hwnd = self.hwnd
        self._reader = ocr.Reader(lambda: user32.PostMessageW(hwnd, WM_OCR, 0, 0))
        self.redraw()
        user32.SetTimer(self.hwnd, TIMER_FOLLOW, FOLLOW_MS, None)
        user32.SetTimer(self.hwnd, TIMER_CURSOR, CURSOR_MS, None)
        user32.SetTimer(self.hwnd, TIMER_CHAT, CHAT_MS, None)
        self._follow()

    def _register(self, class_name: str, proc: WNDPROC) -> None:
        klass = WNDCLASSEXW()
        klass.cbSize = ctypes.sizeof(WNDCLASSEXW)
        klass.lpfnWndProc = proc
        klass.hInstance = kernel32.GetModuleHandleW(None)
        klass.hCursor = user32.LoadCursorW(None, wintypes.LPCWSTR(IDC_ARROW))
        klass.hIcon = self._icon
        klass.hIconSm = self._icon
        klass.lpszClassName = class_name
        if not user32.RegisterClassExW(ctypes.byref(klass)):
            raise _last_error("RegisterClassExW")

    def _create(self, class_name: str, extra_style: int) -> int:
        ex_style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | extra_style
        hwnd = user32.CreateWindowExW(
            ex_style,
            class_name,
            "Harebourg UX",
            WS_POPUP,
            0,
            0,
            100,
            100,
            None,
            None,
            kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise _last_error("CreateWindowExW")
        return hwnd

    def _add_tray(self) -> None:
        nid = self._nid
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._icon
        nid.szTip = "Harebourg UX"
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            raise _last_error("Shell_NotifyIconW")
        self._tray_added = True

    def _remove_tray(self) -> None:
        if not self._tray_added:
            return
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        self._tray_added = False

    def _show_tray_menu(self) -> None:
        menu = user32.CreatePopupMenu()
        setup_flags = MF_STRING | (MF_CHECKED if self.setup else 0)
        user32.AppendMenuW(menu, setup_flags, CMD_SETUP, "Régler la carte")
        chat_flags = MF_STRING | (MF_CHECKED if self.chat_setup else 0)
        user32.AppendMenuW(menu, chat_flags, CMD_CHAT, "Régler le chat")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        for command_id, action in BIND_COMMANDS.items():
            flags = MF_STRING | (MF_CHECKED if self.rebinding == action else 0)
            text = f"{binds.ACTION_NAMES[action]} : {self._label(self.binds[action])}"
            user32.AppendMenuW(menu, flags, command_id, text)
        reset_flags = MF_STRING | (MF_GRAYED if self.binds == dict(binds.DEFAULTS) else 0)
        user32.AppendMenuW(menu, reset_flags, CMD_BIND_RESET, "Touches par défaut")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_HIDE, "Afficher" if self.hidden else "Masquer")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_QUIT, "Quitter")
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self.hwnd)
        command = user32.TrackPopupMenu(
            menu,
            TPM_RIGHTALIGN | TPM_BOTTOMALIGN | TPM_RETURNCMD,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if command == CMD_QUIT:
            user32.DestroyWindow(self.hwnd)
        elif command == CMD_SETUP:
            self._toggle_setup()
        elif command == CMD_CHAT:
            self._toggle_chat_setup()
        elif command == CMD_HIDE:
            self._set_hidden(not self.hidden)
        elif command in BIND_COMMANDS:
            self._toggle_rebind(BIND_COMMANDS[command])
        elif command == CMD_BIND_RESET:
            self._reset_binds()

    def _set_hidden(self, hidden: bool) -> None:
        # Only the windows go away. Hotkeys, mouse buttons and chat reading keep running.
        self.hidden = hidden
        self._follow()
        self.redraw_map()

    def _register_hotkeys(self) -> None:
        for ident, virtual_key, label in HOTKEYS:
            if not user32.RegisterHotKey(self.hwnd, ident, HOTKEY_MODS, virtual_key):
                code = ctypes.get_last_error()
                if code == ERROR_HOTKEY_ALREADY_REGISTERED:
                    raise RuntimeError(f"{label} est déjà utilisé par un autre programme.")
                raise RuntimeError(f"Impossible d'enregistrer {label} ({code}).")

    def _label(self, bind: Bind) -> str:
        return binds.label(bind, _key_char)

    def _register_binds(self) -> None:
        errors = []
        for action in binds.ACTIONS:
            error = self._register_bind(action)
            if error:
                errors.append(error)
                self.binds[action] = binds.DEFAULTS[action]
        if errors and self.binds[binds.MARK_SELF] == self.binds[binds.PIN]:
            for action in binds.ACTIONS:
                self._unregister_bind(action)
            self.binds = dict(binds.DEFAULTS)
        if errors:
            _report(RuntimeError("\n".join([*errors, "Touche par défaut utilisée."])))

    def _register_bind(self, action: str) -> str | None:
        """Mouse binds go through the hook; keyboard binds are registered hotkeys."""

        bind = self.binds[action]
        if bind.button:
            return None
        if user32.RegisterHotKey(self.hwnd, ACTION_IDS[action], bind.mods | MOD_NOREPEAT, bind.key):
            return None
        code = ctypes.get_last_error()
        if code == ERROR_HOTKEY_ALREADY_REGISTERED:
            return f"{self._label(bind)} est déjà utilisée par un autre programme."
        return f"Impossible d'enregistrer {self._label(bind)} ({code})."

    def _unregister_bind(self, action: str) -> None:
        if not self.binds[action].button:
            user32.UnregisterHotKey(self.hwnd, ACTION_IDS[action])

    def _taken(self, action: str) -> dict[Bind, str]:
        taken = {Bind.keyboard(vk, MOD_SHIFT): label for _, vk, label in HOTKEYS}
        for other in binds.ACTIONS:
            if other != action:
                taken[self.binds[other]] = binds.ACTION_NAMES[other]
        return taken

    def _toggle_rebind(self, action: str) -> None:
        if self.rebinding == action:
            self._end_rebind()
            return
        if self.setup:
            self._leave_setup(save=True)
        if self.chat_setup:
            self._leave_chat_setup(save=True)
        self._set_hidden(False)
        if not self._key_hook:
            hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._key_proc, None, 0)
            if not hook:
                _report(_last_error("SetWindowsHookExW"))
                return
            self._key_hook = hook
        self.rebinding = action
        self._bind_error = None
        self.redraw()

    def _end_rebind(self) -> None:
        self.rebinding = None
        self._bind_error = None
        if self._key_hook:
            user32.UnhookWindowsHookEx(self._key_hook)
            self._key_hook = wintypes.HANDLE(0)
        self.redraw()

    def _apply_bind(self, bind: Bind) -> None:
        action = self.rebinding
        if action is None:
            return
        if bind.key == VK_ESCAPE:
            self._end_rebind()
            return
        error = binds.problem(bind, self._taken(action))
        if error is None and bind != self.binds[action]:
            old = self.binds[action]
            self._unregister_bind(action)
            self.binds[action] = bind
            error = self._register_bind(action)
            if error:
                self.binds[action] = old
                self._register_bind(action)
            else:
                self._save_binds()
        if error:
            self._bind_error = error
            self.redraw()
            return
        self._end_rebind()

    def _reset_binds(self) -> None:
        if self.rebinding is not None:
            self._end_rebind()
        for action in binds.ACTIONS:
            self._unregister_bind(action)
        self.binds = dict(binds.DEFAULTS)
        self._save_binds()
        self.redraw()

    def _save_binds(self) -> None:
        try:
            profiles.save_binds(self.binds)
        except OSError as exc:
            _report(exc)

    def _install_side_buttons(self) -> None:
        # RegisterHotKey cannot see mouse buttons. A low-level hook is delivered
        # on this thread and is not injected into the game. A bound button is
        # eaten here, the same way a registered hotkey is.
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, None, 0)
        if not hook:
            raise _last_error("SetWindowsHookExW")
        self._mouse_hook = hook

    def _on_mouse(self, nCode: int, wparam: int, lparam: int) -> int:
        message = int(wparam)
        button = _hook_button(message, lparam) if nCode == HC_ACTION else 0
        if button:
            down = message in (WM_XBUTTONDOWN, WM_MBUTTONDOWN)
            if self.rebinding is not None:
                if down:
                    user32.PostMessageW(self.hwnd, WM_BIND_MOUSE, button, 0)
                return 1
            for action, bind in self.binds.items():
                if bind.button == button:
                    if down:
                        user32.PostMessageW(self.hwnd, WM_SIDE_BUTTON, ACTION_IDS[action], 0)
                    return 1
        return int(user32.CallNextHookEx(self._mouse_hook, nCode, wparam, lparam))

    def _on_capture_key(self, nCode: int, wparam: int, lparam: int) -> int:
        # Only installed while waiting for a new bind. The key is eaten so it
        # does not reach the game or trigger a hotkey.
        if nCode == HC_ACTION and self.rebinding is not None and int(wparam) in (WM_KEYDOWN, WM_SYSKEYDOWN):
            vk = int(ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode)
            if vk not in binds.MODIFIER_KEYS:
                user32.PostMessageW(self.hwnd, WM_BIND_KEY, vk, _held_mods())
                return 1
        return int(user32.CallNextHookEx(self._key_hook, nCode, wparam, lparam))

    def redraw(self) -> None:
        dpi = user32.GetDpiForWindow(self.hwnd) or 96
        self._scale = dpi / 96
        if self.rebinding is not None:
            hint = self._bind_hint(self.rebinding)
        elif self.chat_setup:
            hint = HINT_CHAT
        elif self.setup:
            hint = HINT_SETUP
        else:
            hint = self._play_hint()
        width_dip, height_dip = hud_dip(len(hint))
        width = max(1, round(width_dip * self._scale))
        height = max(1, round(height_dip * self._scale))
        surface = self._hud_layer.begin(width, height)
        surface.draw_hud(
            self._scale,
            self.hud.rotation,
            (self._map_status(), self._chat_status()),
            hint,
        )
        self._hud_layer.present()

    def _play_hint(self) -> tuple[HintLine, ...]:
        mark = self._label(self.binds[binds.MARK_SELF])
        pin = self._label(self.binds[binds.PIN])
        return (
            HINT_DIRECTIONS,
            (Key(mark), "moi", Key(pin), "cible", Key("Maj"), "+", Key("Suppr"), "effacer la cible"),
        )

    def _bind_hint(self, action: str) -> tuple[HintLine, ...]:
        if self._bind_error:
            detail: HintLine = (self._bind_error,)
        else:
            detail = ("Une touche (Ctrl, Maj, Alt possibles) ou", Key("Souris 3"), Key("4"), Key("5"))
        return ((f"Nouvelle touche : {binds.ACTION_NAMES[action]}", Key("Échap"), "annuler"), detail)

    def redraw_map(self) -> None:
        if self._client is None:
            self._show_map(False)
            return
        _, _, width, height = self._client
        if self.chat_setup:
            surface = self._map_layer.begin(width, height)
            surface.draw_chat_setup(self.chat_region, self._map_scale())
            self._map_layer.present()
            self._show_map(True)
            return
        if self.projection is None:
            self._show_map(False)
            return
        surface = self._map_layer.begin(width, height)
        marks = MapMarks() if self.setup else self._marks()
        surface.draw_map(self.layout, self.projection, marks, self._map_scale(), setup=self.setup)
        self._map_layer.present()
        self._show_map(True)

    def _map_scale(self) -> float:
        return (user32.GetDpiForWindow(self.map_hwnd) or 96) / 96

    def _map_status(self) -> Status:
        if self._client is None:
            return Status(Level.ERROR, "Dofus introuvable")
        if self.setup:
            return Status(Level.ACTIVE, "Réglage de la carte")
        if self.projection is None:
            return Status(Level.WARN, "Carte non réglée")
        if self.self_cell is None:
            mark = self._label(self.binds[binds.MARK_SELF])
            return Status(Level.WARN, f"Carte prête, marquez votre case : {mark}")
        return Status(Level.OK, "Carte prête")

    def _chat_status(self) -> Status:
        if self.chat_setup:
            return Status(Level.ACTIVE, "Réglage du chat")
        if self._reader is not None and self._reader.error:
            return Status(Level.ERROR, f"OCR : {self._reader.error}")
        if self._client is None:
            return Status(Level.IDLE, "Chat en attente")
        if self.chat_region is None:
            return Status(Level.WARN, "Chat non réglé")
        if self._chat_speaker:
            return Status(Level.OK, f"Chat lu : {self._chat_speaker}")
        return Status(Level.OK, "Chat lu")

    def _marks(self) -> MapMarks:
        rotation = self.hud.rotation
        landing = None
        aim = None
        if self.self_cell is not None and rotation is not None:
            if self.hover is not None:
                landing = landing_cell(self.self_cell, self.hover, rotation)
            if self.pin_cell is not None:
                aim = aim_cell(self.self_cell, self.pin_cell, rotation)
        return MapMarks(
            hover=self.hover,
            self_cell=self.self_cell,
            landing=landing,
            aim=aim,
            pin=self.pin_cell,
        )

    def _follow(self) -> None:
        target = _find_dofus()
        self._dofus = target
        if target and user32.IsIconic(target):
            self._on_client_changed(None)
            self._set_visible(False)
            return
        client = _client_area(target) if target else None
        if client != self._client:
            self._on_client_changed(client)
        if client is not None:
            # Re-asserting both every tick keeps the HUD above the map.
            flags = SWP_NOSIZE | SWP_NOACTIVATE
            user32.SetWindowPos(self.map_hwnd, HWND_TOPMOST, client[0], client[1], 0, 0, flags)
        x, y = self._anchor(client)
        flags = SWP_NOSIZE | SWP_NOACTIVATE | (0 if self.hidden else SWP_SHOWWINDOW)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, 0, 0, flags)
        self._set_visible(True)

    def _on_client_changed(self, client: tuple[int, int, int, int] | None) -> None:
        old_size = self._client[2:] if self._client else None
        new_size = client[2:] if client else None
        if new_size != old_size and self.setup:
            self._leave_setup(save=False)
        if new_size != old_size and self.chat_setup:
            self._leave_chat_setup(save=False)
        self._client = client
        if client is not None:
            flags = SWP_NOSIZE | SWP_NOACTIVATE
            user32.SetWindowPos(self.map_hwnd, HWND_TOPMOST, client[0], client[1], 0, 0, flags)
        if new_size != old_size:
            # A profile only applies to the client size it was made for.
            self.projection = profiles.find(MAP_NAME, *new_size) if new_size else None
            self.chat_region = profiles.find_chat(*new_size) if new_size else None
            self._chat_frame = None
            self._watch.reset()
            self._chat_speaker = None
            self.hover = None
            self.redraw()
            self.redraw_map()

    def _anchor(self, client: tuple[int, int, int, int] | None) -> tuple[int, int]:
        margin = round(MARGIN_DIP * self._scale)
        width = self._hud_layer.width
        if client is not None:
            x, y, client_width, _ = client
            return x + client_width - width - margin, y + margin
        work = RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
        return work.right - width - margin, work.top + margin

    def _set_visible(self, visible: bool) -> None:
        visible = visible and not self.hidden
        if visible == self._visible:
            return
        user32.ShowWindow(self.hwnd, SW_SHOWNA if visible else SW_HIDE)
        self._visible = visible

    def _show_map(self, visible: bool) -> None:
        visible = visible and not self.hidden
        if visible == self._map_visible:
            return
        user32.ShowWindow(self.map_hwnd, SW_SHOWNA if visible else SW_HIDE)
        self._map_visible = visible

    def _cursor_client(self) -> tuple[int, int] | None:
        if self._client is None:
            return None
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        x, y, width, height = self._client
        local_x, local_y = point.x - x, point.y - y
        if not (0 <= local_x < width and 0 <= local_y < height):
            return None
        return local_x, local_y

    def _cursor_cell(self) -> Cell | None:
        point = self._cursor_client()
        if point is None or self.projection is None:
            return None
        cell = self.projection.cell_at(*point)
        return cell if self.layout.contains(cell) else None

    def _poll_cursor(self) -> None:
        if self.setup or self.chat_setup or not self._map_visible:
            return
        cell = self._cursor_cell()
        if cell != self.hover:
            self.hover = cell
            self.redraw_map()

    def _toggle_setup(self) -> None:
        if self.setup:
            self._leave_setup(save=True)
        else:
            self._enter_setup()

    def _enter_setup(self) -> None:
        if self._client is None:
            return
        if self.chat_setup:
            self._leave_chat_setup(save=True)
        if self.rebinding is not None:
            self._end_rebind()
        self._set_hidden(False)
        _, _, width, height = self._client
        self._setup_backup = self.projection
        if self.projection is None:
            cell = profiles.cell_size_hint(width, height) or DEFAULT_CELL
            margin = round(FIT_MARGIN_DIP * self._scale)
            self.projection = Projection(0, 0, *cell).fit(self.layout, width, height, margin)
        self.setup = True
        self.hover = None
        self._set_click_through(False)
        self._focus_map()
        self.redraw()
        self.redraw_map()

    def _leave_setup(self, save: bool) -> None:
        self._end_drag()
        self._set_click_through(True)
        self.setup = False
        if self._dofus:
            user32.SetForegroundWindow(self._dofus)
        if not save:
            self.projection = self._setup_backup
        elif self._client is not None and self.projection is not None:
            _, _, width, height = self._client
            try:
                profiles.save(MAP_NAME, width, height, self.projection)
            except OSError as exc:
                _report(exc)
            else:
                self.projection = profiles.find(MAP_NAME, width, height) or self.projection
        self._setup_backup = None
        self.redraw()
        self.redraw_map()

    def _set_click_through(self, enabled: bool) -> None:
        style = user32.GetWindowLongPtrW(self.map_hwnd, GWL_EXSTYLE)
        if enabled:
            style |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        else:
            style &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        user32.SetWindowLongPtrW(self.map_hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(
            self.map_hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )

    def _focus_map(self) -> None:
        user32.SetForegroundWindow(self.map_hwnd)
        user32.SetFocus(self.map_hwnd)

    def _handle_at(self, x: int, y: int) -> tuple[str, float, float] | None:
        """Corner name and the opposite corner, which stays put while scaling."""

        if self.projection is None:
            return None
        bounds = self.projection.bounds(self.layout)
        if bounds is None:
            return None
        left, top, right, bottom = bounds
        reach = max(14, round(HANDLE_DIP * self._map_scale())) // 2 + 8
        corners = (
            ("nw", left, top, float(right), float(bottom)),
            ("ne", right, top, float(left), float(bottom)),
            ("sw", left, bottom, float(right), float(top)),
            ("se", right, bottom, float(left), float(top)),
        )
        best: tuple[str, float, float] | None = None
        best_d = reach * reach + 1
        for name, hx, hy, ax, ay in corners:
            distance = (x - hx) ** 2 + (y - hy) ** 2
            if distance <= reach * reach and distance < best_d:
                best = (name, ax, ay)
                best_d = distance
        return best

    def _start_drag(self, x: int, y: int) -> None:
        if self.projection is None or self.projection.bounds(self.layout) is None:
            return
        hit = self._handle_at(x, y)
        if hit is None:
            self._drag = ("move", x, y, self.projection, (0.0, 0.0))
        else:
            _, anchor_x, anchor_y = hit
            self._drag = ("scale", x, y, self.projection, (anchor_x, anchor_y))
        user32.SetCapture(self.map_hwnd)

    def _drag_to(self, x: int, y: int) -> None:
        if self._drag is None:
            return
        mode, start_x, start_y, start, (anchor_x, anchor_y) = self._drag
        if mode == "move":
            self.projection = start.moved(x - start_x, y - start_y)
        else:
            start_span = math.hypot(start_x - anchor_x, start_y - anchor_y)
            if start_span < 1:
                return
            factor = math.hypot(x - anchor_x, y - anchor_y) / start_span
            if start.cell_width * factor < MIN_CELL_WIDTH:
                factor = MIN_CELL_WIDTH / start.cell_width
            self.projection = start.scaled_uniform(factor, anchor_x, anchor_y)
        self.redraw_map()

    def _end_drag(self) -> None:
        self._drag = None
        if user32.GetCapture() == self.map_hwnd:
            user32.ReleaseCapture()

    def _toggle_chat_setup(self) -> None:
        if self.chat_setup:
            self._leave_chat_setup(save=True)
        else:
            self._enter_chat_setup()

    def _enter_chat_setup(self) -> None:
        if self._client is None:
            return
        if self.setup:
            self._leave_setup(save=True)
        if self.rebinding is not None:
            self._end_rebind()
        self._set_hidden(False)
        self._chat_backup = self.chat_region
        self.chat_setup = True
        self.hover = None
        self._set_click_through(False)
        self._focus_map()
        self.redraw()
        self.redraw_map()

    def _leave_chat_setup(self, save: bool) -> None:
        self._chat_drag = None
        if user32.GetCapture() == self.map_hwnd:
            user32.ReleaseCapture()
        self._set_click_through(True)
        self.chat_setup = False
        if self._dofus:
            user32.SetForegroundWindow(self._dofus)
        if not save:
            self.chat_region = self._chat_backup
        elif self._client is not None and self.chat_region is not None:
            _, _, width, height = self._client
            try:
                profiles.save_chat(width, height, self.chat_region)
            except OSError as exc:
                _report(exc)
        self._chat_backup = None
        self._chat_frame = None
        self._watch.reset()
        self._chat_speaker = None
        self.redraw()
        self.redraw_map()

    def _chat_drag_to(self, x: int, y: int) -> None:
        if self._chat_drag is None or self._client is None:
            return
        _, _, width, height = self._client
        start_x, start_y = self._chat_drag
        x = min(max(x, 0), width)
        y = min(max(y, 0), height)
        left, right = sorted((start_x, x))
        top, bottom = sorted((start_y, y))
        if right - left >= MIN_CHAT_PX and bottom - top >= MIN_CHAT_PX:
            self.chat_region = (left, top, right - left, bottom - top)
            self.redraw_map()

    def _poll_chat(self) -> None:
        reader = self._reader
        if reader is None or reader.unavailable or self.setup or self.chat_setup:
            return
        if self._client is None or self.chat_region is None:
            return
        client_x, client_y, _, _ = self._client
        x, y, width, height = self.chat_region
        left, top = client_x + x, client_y + y
        try:
            plain = _capture(left, top, width, height, 1)
            if plain[2] == self._chat_frame:
                return
            self._chat_frame = plain[2]
            # Either size can drop a glyph the other one reads; chat.pick keeps the better one.
            scale = min(CAPTURE_SCALE, reader.max_dimension / max(width, height))
            reader.submit([plain, _capture(left, top, width, height, scale)])
        except RuntimeError:
            self._chat_frame = None

    def _on_ocr(self) -> None:
        if self._reader is None:
            return
        results = self._reader.take()
        if not results:
            self.redraw()
            return
        chosen = [chat.pick(readings) for readings in results]
        try:
            profiles.LAST_OCR_PATH.parent.mkdir(parents=True, exist_ok=True)
            profiles.LAST_OCR_PATH.write_text("\n".join(chosen[-1]) + "\n", encoding="utf-8")
        except OSError:
            pass
        found = None
        for lines in chosen:
            found = self._watch.feed(lines) or found
        if found is not None:
            self._chat_speaker = found.speaker
            if found.rotation != self.hud.rotation:
                self.hud.set_rotation(found.rotation)
                self.redraw_map()
        self.redraw()

    def _on_hotkey(self, ident: int) -> None:
        if ident in (ID_STRAIGHT, ID_CLOCKWISE, ID_HALF, ID_COUNTER, ID_BUMP):
            self._chat_speaker = None
        if ident == ID_STRAIGHT:
            self.hud.set_rotation(Rotation.STRAIGHT)
        elif ident == ID_CLOCKWISE:
            self.hud.set_rotation(Rotation.CLOCKWISE)
        elif ident == ID_HALF:
            self.hud.set_rotation(Rotation.HALF)
        elif ident == ID_COUNTER:
            self.hud.set_rotation(Rotation.COUNTERCLOCKWISE)
        elif ident == ID_BUMP:
            self.hud.bump()
        if ident in (ID_STRAIGHT, ID_CLOCKWISE, ID_HALF, ID_COUNTER, ID_BUMP):
            self._watch.correct(self.hud.rotation)
        elif ident == ID_MARK_SELF:
            cell = self._cursor_cell()
            if cell is not None:
                self.self_cell = cell
        elif ident == ID_PIN:
            cell = self._cursor_cell()
            if cell is not None:
                self.pin_cell = cell
        elif ident == ID_CLEAR_PIN:
            self.pin_cell = None
        self.redraw()
        self.redraw_map()

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_TRAY and int(lparam) & 0xFFFF in (WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU):
            self._show_tray_menu()
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_HOTKEY or msg == WM_SIDE_BUTTON:
            self._on_hotkey(int(wparam))
            return 0
        if msg == WM_OCR:
            self._on_ocr()
            return 0
        if msg == WM_BIND_MOUSE:
            self._apply_bind(Bind.mouse(int(wparam)))
            return 0
        if msg == WM_BIND_KEY:
            self._apply_bind(Bind.keyboard(int(wparam), int(lparam)))
            return 0
        if msg == WM_TIMER:
            if wparam == TIMER_CURSOR:
                self._poll_cursor()
                return 0
            if wparam == TIMER_CHAT:
                self._poll_chat()
                return 0
            self._follow()
            if os.environ.get("HAREBOURG_SMOKE"):
                self._smoke_ticks += 1
                if self._smoke_ticks > 8:
                    user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DPICHANGED:
            self.redraw()
            self._follow()
            return 0
        if msg == WM_DESTROY:
            self._remove_tray()
            user32.PostQuitMessage(0)
            return 0
        return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))

    def _map_wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        # Mouse input only arrives here in setup mode; in play the window is click-through.
        if msg == WM_MOUSEACTIVATE:
            return MA_ACTIVATE if self.setup or self.chat_setup else MA_NOACTIVATE
        if self.chat_setup:
            return self._chat_setup_proc(hwnd, msg, wparam, lparam)
        if msg == WM_KEYDOWN and self.setup and int(wparam) == VK_ESCAPE:
            self._leave_setup(save=True)
            return 0
        if msg == WM_SETCURSOR and self.setup:
            point = self._cursor_client()
            hit = self._handle_at(*point) if point is not None else None
            if hit is None:
                cursor = IDC_SIZEALL
            elif hit[0] in ("nw", "se"):
                cursor = IDC_SIZENWSE
            else:
                cursor = IDC_SIZENESW
            user32.SetCursor(user32.LoadCursorW(None, wintypes.LPCWSTR(cursor)))
            return 1
        if msg == WM_LBUTTONDOWN and self.setup:
            self._focus_map()
            self._start_drag(*_mouse_point(lparam))
            return 0
        if msg == WM_MOUSEMOVE and self._drag is not None:
            self._drag_to(*_mouse_point(lparam))
            return 0
        if msg == WM_LBUTTONUP and self._drag is not None:
            self._end_drag()
            return 0
        if msg == WM_CAPTURECHANGED:
            self._drag = None
            return 0
        if msg == WM_DPICHANGED:
            self.redraw_map()
            return 0
        return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))

    def _chat_setup_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_KEYDOWN and int(wparam) == VK_ESCAPE:
            self._leave_chat_setup(save=True)
            return 0
        if msg == WM_SETCURSOR:
            user32.SetCursor(user32.LoadCursorW(None, wintypes.LPCWSTR(IDC_CROSS)))
            return 1
        if msg == WM_LBUTTONDOWN:
            self._focus_map()
            self._chat_drag = _mouse_point(lparam)
            user32.SetCapture(self.map_hwnd)
            return 0
        if msg == WM_MOUSEMOVE and self._chat_drag is not None:
            self._chat_drag_to(*_mouse_point(lparam))
            return 0
        if msg == WM_LBUTTONUP and self._chat_drag is not None:
            self._chat_drag_to(*_mouse_point(lparam))
            self._chat_drag = None
            user32.ReleaseCapture()
            return 0
        if msg == WM_CAPTURECHANGED:
            self._chat_drag = None
            return 0
        if msg == WM_DPICHANGED:
            self.redraw_map()
            return 0
        return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))

    def close(self) -> None:
        if self._reader is not None:
            self._reader.stop()
            self._reader = None
        for ident, _, _ in HOTKEYS:
            user32.UnregisterHotKey(self.hwnd, ident)
        for action in binds.ACTIONS:
            self._unregister_bind(action)
        for hook in (self._mouse_hook, self._key_hook):
            if hook:
                user32.UnhookWindowsHookEx(hook)
        self._mouse_hook = wintypes.HANDLE(0)
        self._key_hook = wintypes.HANDLE(0)
        self._remove_tray()
        if self._icon:
            user32.DestroyIcon(self._icon)
            self._icon = wintypes.HICON(0)
        if self.hwnd:
            user32.KillTimer(self.hwnd, TIMER_FOLLOW)
            user32.KillTimer(self.hwnd, TIMER_CURSOR)
            user32.KillTimer(self.hwnd, TIMER_CHAT)
        if self.map_hwnd:
            user32.DestroyWindow(self.map_hwnd)
        self._hud_layer.release()
        self._map_layer.release()
        shutdown()


def _find_dofus() -> int:
    found: list[tuple[int, int, bool]] = []

    @WNDENUMPROC
    def visit(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value
        class_text = class_name.value
        named = "dofus" in title.casefold()
        if not named and class_text != "UnityWndClass":
            return True
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        area = max(0, rect.right) * max(0, rect.bottom)
        if area < 400 * 300:
            return True
        found.append((area, int(hwnd), named))
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return 0
    named = [item for item in found if item[2]]
    pool = named or found
    pool.sort(reverse=True)
    return pool[0][1]


def _client_area(hwnd: int) -> tuple[int, int, int, int]:
    """Screen x, y and width, height of a window's client area."""

    rect = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right, rect.bottom


def _capture(x: int, y: int, width: int, height: int, scale: float) -> tuple[int, int, bytes]:
    """Top-down BGRA pixels of one screen rectangle, scaled.

    Without CAPTUREBLT, BitBlt leaves out layered windows, so the overlay's own
    HUD and grid never end up in the OCR image.
    """

    out_width = max(1, round(width * scale))
    out_height = max(1, round(height * scale))
    screen = user32.GetDC(None)
    if not screen:
        raise _last_error("GetDC")
    dc = gdi32.CreateCompatibleDC(screen)
    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = out_width
    header.biHeight = -out_height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    dib = gdi32.CreateDIBSection(dc, ctypes.byref(header), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    try:
        if not dib or not bits.value:
            raise _last_error("CreateDIBSection capture")
        previous = gdi32.SelectObject(dc, dib)
        gdi32.SetStretchBltMode(dc, HALFTONE)
        gdi32.SetBrushOrgEx(dc, 0, 0, None)
        ok = gdi32.StretchBlt(dc, 0, 0, out_width, out_height, screen, x, y, width, height, SRCCOPY)
        gdi32.SelectObject(dc, previous)
        if not ok:
            raise _last_error("StretchBlt")
        return out_width, out_height, ctypes.string_at(bits.value, out_width * out_height * 4)
    finally:
        if dib:
            gdi32.DeleteObject(dib)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)


def _hook_button(message: int, lparam: int) -> int:
    """3, 4 or 5 for a middle or side button event seen by the mouse hook, else 0."""

    if message in (WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK):
        return 3
    if message in (WM_XBUTTONDOWN, WM_XBUTTONUP, WM_XBUTTONDBLCLK):
        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        button = (int(info.mouseData) >> 16) & 0xFFFF
        return {XBUTTON1: 4, XBUTTON2: 5}.get(button, 0)
    return 0


def _held_mods() -> int:
    mods = 0
    for vk, flag in ((VK_SHIFT, binds.MOD_SHIFT), (VK_CONTROL, binds.MOD_CONTROL), (VK_MENU, binds.MOD_ALT)):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            mods |= flag
    return mods


def _key_char(vk: int) -> str:
    code = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_CHAR) & 0xFFFF
    return chr(code) if code else ""


def _mouse_point(lparam: int) -> tuple[int, int]:
    value = int(lparam)
    return ctypes.c_short(value & 0xFFFF).value, ctypes.c_short((value >> 16) & 0xFFFF).value


def _report(exc: BaseException) -> None:
    user32.MessageBoxW(None, str(exc), "Harebourg UX", 0x00000010)


def _arrow_icon(size: int = 32) -> wintypes.HICON:
    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = size
    header.biHeight = -size
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    dc = gdi32.CreateCompatibleDC(None)
    color = gdi32.CreateDIBSection(dc, ctypes.byref(header), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    if not color or not bits.value:
        raise _last_error("CreateDIBSection icon")
    pixel_count = size * size
    raw = (ctypes.c_ubyte * (pixel_count * 4)).from_address(bits.value)
    amber = (62, 184, 242, 255)

    def plot(x: int, y: int, color_bgra: tuple[int, int, int, int]) -> None:
        if not 0 <= x < size or not 0 <= y < size:
            return
        index = (y * size + x) * 4
        blue, green, red, alpha = color_bgra
        raw[index] = blue * alpha // 255
        raw[index + 1] = green * alpha // 255
        raw[index + 2] = red * alpha // 255
        raw[index + 3] = alpha

    for y in range(5, 18):
        span = 2 + (y - 5) * 10 / 12
        left = round(16 - span)
        right = round(16 + span)
        for x in range(left, right + 1):
            plot(x, y, amber)
    for y in range(16, 27):
        for x in range(12, 21):
            plot(x, y, amber)
    mask = gdi32.CreateBitmap(size, size, 1, 1, None)
    info = ICONINFO(True, 0, 0, mask, color)
    icon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(color)
    gdi32.DeleteObject(mask)
    gdi32.DeleteDC(dc)
    if not icon:
        raise _last_error("CreateIconIndirect")
    return icon


def main() -> None:
    shell32.SetCurrentProcessExplicitAppUserModelID("Harebourg.HarebourgUx")
    enable_dpi_awareness()
    overlay: Overlay | None = None
    try:
        overlay = Overlay()
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
    finally:
        if overlay is not None:
            overlay.close()
