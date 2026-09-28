"""Start the Harebourg overlay. Launched by "Lancer Harebourg UX.bat", or double-click this file."""

from __future__ import annotations

import ctypes
import sys
import traceback
from pathlib import Path

TITLE = "Harebourg UX"
ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "config" / "harebourg.log"
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40
ERROR_ALREADY_EXISTS = 183


def _message(text: str, icon: int = MB_ICONERROR) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, TITLE, icon)


if sys.version_info < (3, 14):
    _message("Python 3.14 ou plus récent est requis.")
    raise SystemExit(1)


def _open_log():
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        return LOG_PATH.open("w", encoding="utf-8", buffering=1)
    except OSError:
        return None


def main() -> int:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel32.CreateMutexW(None, False, "Local\\HarebourgUx")
    if mutex and ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _message("Harebourg UX est déjà lancé : utilisez son icône dans la zone de notification.", MB_ICONINFORMATION)
        return 0

    log = _open_log()
    if sys.stderr is None and log is not None:
        # pythonw has no console; tracebacks from window callbacks would be lost.
        sys.stderr = log

    sys.path.insert(0, str(ROOT / "src"))
    try:
        import overlay

        overlay.main()
    except Exception as exc:
        if log is not None:
            traceback.print_exc(file=log)
            log.flush()
        detail = str(exc) or type(exc).__name__
        where = f"\n\nDétails : {LOG_PATH}" if log is not None else ""
        _message(f"Harebourg UX s'est arrêté.\n\n{detail}{where}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
