"""Windows OCR (Windows.Media.Ocr) through combase. No pip package, no network.

This module only turns BGRA pixels into text lines. Screen capture stays in
overlay.py. Recognition runs on a worker thread so the cursor poll never waits.
"""

from __future__ import annotations

import ctypes
import threading
import time
import uuid
from collections.abc import Callable
from ctypes import wintypes

combase = ctypes.WinDLL("combase", use_last_error=True)

HSTRING = ctypes.c_void_p
RO_INIT_MULTITHREADED = 1
BITMAP_PIXEL_FORMAT_BGRA8 = 87
BITMAP_ALPHA_MODE_IGNORE = 2
BITMAP_BUFFER_ACCESS_WRITE = 2
ASYNC_STARTED = 0
ASYNC_COMPLETED = 1
RECOGNIZE_TIMEOUT_S = 5.0
PREFERRED_LANGUAGES = ("fr-FR", "fr")


def _iid(text: str) -> ctypes.Array:
    return (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(text).bytes_le)


IID_OCR_ENGINE_STATICS = _iid("5bffa85a-3384-3540-9940-699120d428a8")
IID_SOFTWARE_BITMAP_FACTORY = _iid("c99feb69-2d62-4d47-a6b3-4fdb6a07fdf8")
IID_LANGUAGE_FACTORY = _iid("9b0252ac-0c27-44f8-b792-9793fb66c63e")
IID_MEMORY_BUFFER = _iid("fbc4dd2a-245b-11e4-af98-689423260cf8")
IID_MEMORY_BUFFER_BYTE_ACCESS = _iid("5b0d3235-4dba-4d44-865e-8f1d0e4fd04d")
IID_CLOSABLE = _iid("30d5a829-7fa4-4026-83bb-d75bae4ea99e")
IID_ASYNC_INFO = _iid("00000036-0000-0000-c000-000000000046")


class BitmapPlaneDescription(ctypes.Structure):
    _fields_ = (
        ("StartIndex", ctypes.c_int32),
        ("Width", ctypes.c_int32),
        ("Height", ctypes.c_int32),
        ("Stride", ctypes.c_int32),
    )


combase.RoInitialize.argtypes = [ctypes.c_int]
combase.RoInitialize.restype = ctypes.c_long
combase.RoUninitialize.argtypes = []
combase.RoUninitialize.restype = None
combase.WindowsCreateString.argtypes = [wintypes.LPCWSTR, ctypes.c_uint32, ctypes.POINTER(HSTRING)]
combase.WindowsCreateString.restype = ctypes.HRESULT
combase.WindowsDeleteString.argtypes = [HSTRING]
combase.WindowsDeleteString.restype = ctypes.HRESULT
combase.WindowsGetStringRawBuffer.argtypes = [HSTRING, ctypes.POINTER(ctypes.c_uint32)]
combase.WindowsGetStringRawBuffer.restype = ctypes.c_void_p
combase.RoGetActivationFactory.argtypes = [HSTRING, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
combase.RoGetActivationFactory.restype = ctypes.HRESULT


class OcrUnavailable(RuntimeError):
    pass


def _call(obj: ctypes.c_void_p, index: int, *args: object, argtypes: tuple = ()) -> None:
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(table[index])
    method(obj, *args)


def _release(obj: ctypes.c_void_p) -> None:
    if obj:
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(obj)


def _query(obj: ctypes.c_void_p, iid: ctypes.Array) -> ctypes.c_void_p:
    out = ctypes.c_void_p()
    _call(obj, 0, ctypes.byref(iid), ctypes.byref(out), argtypes=(ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)))
    return out


def _out(obj: ctypes.c_void_p, index: int, *args: object, argtypes: tuple = ()) -> ctypes.c_void_p:
    out = ctypes.c_void_p()
    _call(obj, index, *args, ctypes.byref(out), argtypes=(*argtypes, ctypes.POINTER(ctypes.c_void_p)))
    return out


class _HString:
    def __init__(self, text: str) -> None:
        self.handle = HSTRING()
        combase.WindowsCreateString(text, len(text), ctypes.byref(self.handle))

    def __enter__(self) -> HSTRING:
        return self.handle

    def __exit__(self, *_: object) -> None:
        combase.WindowsDeleteString(self.handle)


def _read_hstring(handle: HSTRING) -> str:
    if not handle:
        return ""
    length = ctypes.c_uint32()
    raw = combase.WindowsGetStringRawBuffer(handle, ctypes.byref(length))
    text = ctypes.wstring_at(raw, length.value) if raw else ""
    combase.WindowsDeleteString(handle)
    return text


def _factory(class_name: str, iid: ctypes.Array) -> ctypes.c_void_p:
    out = ctypes.c_void_p()
    with _HString(class_name) as name:
        combase.RoGetActivationFactory(name, ctypes.byref(iid), ctypes.byref(out))
    return out


class Engine:
    """One OCR engine. Create and use it on the same MTA thread."""

    def __init__(self) -> None:
        self._engine = ctypes.c_void_p()
        self._statics = _factory("Windows.Media.Ocr.OcrEngine", IID_OCR_ENGINE_STATICS)
        self._bitmaps = _factory("Windows.Graphics.Imaging.SoftwareBitmap", IID_SOFTWARE_BITMAP_FACTORY)
        max_dim = ctypes.c_uint32()
        _call(self._statics, 6, ctypes.byref(max_dim), argtypes=(ctypes.POINTER(ctypes.c_uint32),))
        self.max_dimension = int(max_dim.value) or 2600
        self._engine = self._preferred_engine() or _out(self._statics, 10)
        if not self._engine:
            raise OcrUnavailable("Aucune langue OCR Windows installée.")
        self.language = self._language_tag()

    def _preferred_engine(self) -> ctypes.c_void_p | None:
        languages = _factory("Windows.Globalization.Language", IID_LANGUAGE_FACTORY)
        try:
            for tag in PREFERRED_LANGUAGES:
                with _HString(tag) as name:
                    language = _out(languages, 6, name, argtypes=(HSTRING,))
                try:
                    supported = ctypes.c_bool()
                    _call(
                        self._statics,
                        8,
                        language,
                        ctypes.byref(supported),
                        argtypes=(ctypes.c_void_p, ctypes.POINTER(ctypes.c_bool)),
                    )
                    if supported.value:
                        engine = _out(self._statics, 9, language, argtypes=(ctypes.c_void_p,))
                        if engine:
                            return engine
                finally:
                    _release(language)
        finally:
            _release(languages)
        return None

    def _language_tag(self) -> str:
        language = _out(self._engine, 7)
        try:
            tag = HSTRING()
            _call(language, 6, ctypes.byref(tag), argtypes=(ctypes.POINTER(HSTRING),))
            return _read_hstring(tag)
        finally:
            _release(language)

    def recognize(self, width: int, height: int, bgra: bytes) -> list[str]:
        """Text lines, top to bottom, from a top-down BGRA image."""

        bitmap = self._bitmap(width, height, bgra)
        try:
            operation = _out(self._engine, 6, bitmap, argtypes=(ctypes.c_void_p,))
        finally:
            _release(bitmap)
        try:
            self._wait(operation)
            result = _out(operation, 8)
        finally:
            _release(operation)
        try:
            return self._lines(result)
        finally:
            _release(result)

    def _bitmap(self, width: int, height: int, bgra: bytes) -> ctypes.c_void_p:
        # Screen captures leave alpha at 0, so alpha is ignored rather than premultiplied.
        bitmap = _out(
            self._bitmaps,
            7,
            BITMAP_PIXEL_FORMAT_BGRA8,
            width,
            height,
            BITMAP_ALPHA_MODE_IGNORE,
            argtypes=(ctypes.c_int, ctypes.c_int32, ctypes.c_int32, ctypes.c_int),
        )
        try:
            buffer = _out(bitmap, 15, BITMAP_BUFFER_ACCESS_WRITE, argtypes=(ctypes.c_int,))
            try:
                plane = BitmapPlaneDescription()
                _call(
                    buffer,
                    7,
                    0,
                    ctypes.byref(plane),
                    argtypes=(ctypes.c_int32, ctypes.POINTER(BitmapPlaneDescription)),
                )
                memory = _query(buffer, IID_MEMORY_BUFFER)
                try:
                    reference = _out(memory, 6)
                finally:
                    _release(memory)
                try:
                    self._write(reference, plane, width, height, bgra)
                finally:
                    _close(reference)
                    _release(reference)
            finally:
                # The bitmap stays locked until the buffer is closed; OCR refuses it otherwise.
                _close(buffer)
                _release(buffer)
        except BaseException:
            _release(bitmap)
            raise
        return bitmap

    @staticmethod
    def _write(
        reference: ctypes.c_void_p,
        plane: BitmapPlaneDescription,
        width: int,
        height: int,
        bgra: bytes,
    ) -> None:
        access = _query(reference, IID_MEMORY_BUFFER_BYTE_ACCESS)
        try:
            data = ctypes.c_void_p()
            capacity = ctypes.c_uint32()
            _call(
                access,
                3,
                ctypes.byref(data),
                ctypes.byref(capacity),
                argtypes=(ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)),
            )
            row = width * 4
            base = int(data.value or 0) + plane.StartIndex
            if plane.Stride == row:
                ctypes.memmove(base, bgra, row * height)
            else:
                for y in range(height):
                    ctypes.memmove(base + y * plane.Stride, bgra[y * row : (y + 1) * row], row)
        finally:
            _release(access)

    @staticmethod
    def _wait(operation: ctypes.c_void_p) -> None:
        info = _query(operation, IID_ASYNC_INFO)
        try:
            status = ctypes.c_int()
            deadline = time.monotonic() + RECOGNIZE_TIMEOUT_S
            while True:
                _call(info, 7, ctypes.byref(status), argtypes=(ctypes.POINTER(ctypes.c_int),))
                if status.value != ASYNC_STARTED:
                    break
                if time.monotonic() > deadline:
                    _call(info, 9)
                    raise TimeoutError("OCR trop lent")
                time.sleep(0.005)
            if status.value != ASYNC_COMPLETED:
                code = ctypes.c_long()
                _call(info, 8, ctypes.byref(code), argtypes=(ctypes.POINTER(ctypes.c_long),))
                raise OSError(f"Échec OCR ({code.value & 0xFFFFFFFF:#010x})")
        finally:
            _release(info)

    @staticmethod
    def _lines(result: ctypes.c_void_p) -> list[str]:
        lines = _out(result, 6)
        try:
            size = ctypes.c_uint32()
            _call(lines, 7, ctypes.byref(size), argtypes=(ctypes.POINTER(ctypes.c_uint32),))
            texts = []
            for index in range(size.value):
                line = _out(lines, 6, index, argtypes=(ctypes.c_uint32,))
                try:
                    text = HSTRING()
                    _call(line, 7, ctypes.byref(text), argtypes=(ctypes.POINTER(HSTRING),))
                    texts.append(_read_hstring(text))
                finally:
                    _release(line)
            return texts
        finally:
            _release(lines)

    def close(self) -> None:
        for obj in (self._engine, self._bitmaps, self._statics):
            _release(obj)
        self._engine = self._bitmaps = self._statics = ctypes.c_void_p()


def _close(obj: ctypes.c_void_p) -> None:
    closable = _query(obj, IID_CLOSABLE)
    try:
        _call(closable, 6)
    finally:
        _release(closable)


Image = tuple[int, int, bytes]


class Reader:
    """Recognizes the latest submitted frame on a worker thread.

    A frame is one or more images of the same screen area, for example at two
    scales; each result holds one list of lines per image. Only the newest
    pending frame is kept: a frame that arrives while OCR is busy replaces
    the one waiting. `notify` runs on the worker thread.
    """

    def __init__(self, notify: Callable[[], None]) -> None:
        self._notify = notify
        self._lock = threading.Condition()
        self._pending: list[Image] | None = None
        self._results: list[list[list[str]]] = []
        self._stopped = False
        self.error: str | None = None
        self.unavailable = False
        self.max_dimension = 2600
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="harebourg-ocr", daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def submit(self, images: list[Image]) -> None:
        with self._lock:
            self._pending = images
            self._lock.notify()

    def take(self) -> list[list[list[str]]]:
        with self._lock:
            results, self._results = self._results, []
        return results

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            self._lock.notify()
        self._thread.join(2)

    def _run(self) -> None:
        combase.RoInitialize(RO_INIT_MULTITHREADED)
        engine: Engine | None = None
        try:
            try:
                engine = Engine()
                self.max_dimension = engine.max_dimension
            except (OSError, OcrUnavailable) as exc:
                self.error = str(exc) or "OCR indisponible"
                self.unavailable = True
            finally:
                self._ready.set()
            if engine is None:
                return
            while True:
                with self._lock:
                    while self._pending is None and not self._stopped:
                        self._lock.wait()
                    if self._stopped:
                        return
                    images = self._pending
                    self._pending = None
                try:
                    readings = [engine.recognize(*image) for image in images]
                except (OSError, TimeoutError) as exc:
                    self.error = str(exc) or "OCR"
                    continue
                self.error = None
                with self._lock:
                    self._results.append(readings)
                self._notify()
        finally:
            if engine is not None:
                engine.close()
            combase.RoUninitialize()
