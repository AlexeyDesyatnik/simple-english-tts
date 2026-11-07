"""Opens the Edge app window and remembers its normal bounds and maximized state (ADR-0003).

Without Edge the page opens in the default browser, so the teacher still gets the program.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import logging
import os
import subprocess
import threading
import webbrowser
import winreg
from ctypes import wintypes
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

_log = logging.getLogger(__name__)
_APP_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
_FORMAT_VERSION = 1
_WINDOW_TITLE = "Озвучка"
_EDGE_WINDOW_CLASS = "Chrome_WidgetWin_1"
_SW_SHOWNORMAL = 1
_SW_SHOWMINIMIZED = 2
_SW_SHOWMAXIMIZED = 3
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class WindowPlacement:
    left: int
    top: int
    width: int
    height: int
    maximized: bool = False


class WindowPlacementFile:
    def __init__(self, data_dir: Path):
        self._path = data_dir / "window.json"

    def read(self) -> WindowPlacement | None:
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict) or stored.get("version") != _FORMAT_VERSION:
                return None
            left, top = stored.get("left"), stored.get("top")
            width, height, maximized = stored.get("width"), stored.get("height"), stored.get("maximized")
            if (
                type(left) is not int
                or type(top) is not int
                or type(width) is not int
                or type(height) is not int
                or type(maximized) is not bool
            ):
                return None
            if width <= 0 or height <= 0:
                return None
            return WindowPlacement(left, top, width, height, maximized)
        except (OSError, ValueError):
            return None

    def save(self, placement: WindowPlacement) -> None:
        # Kept separate from settings.json: Core and the window monitor may save at the same time.
        from ozvuchka.library import write_atomically

        stored = {
            "version": _FORMAT_VERSION,
            "left": placement.left,
            "top": placement.top,
            "width": placement.width,
            "height": placement.height,
            "maximized": placement.maximized,
        }
        with contextlib.suppress(OSError):
            write_atomically(self._path, json.dumps(stored, ensure_ascii=False, indent=1).encode())


class _NativeWindows(Protocol):
    def windows(self) -> list[int]: ...

    def placement(self, handle: int) -> tuple[WindowPlacement, bool] | None: ...

    def set_placement(self, handle: int, placement: WindowPlacement) -> None: ...


class WindowMonitor:
    def __init__(
        self, data_dir: Path, native: _NativeWindows | None = None, files: WindowPlacementFile | None = None
    ):
        self._native = native if native is not None else _Windows()
        self._files = files if files is not None else WindowPlacementFile(data_dir)
        self._saved = self._files.read()
        self._known: dict[int, WindowPlacement] = {}

    def check(self) -> None:
        handles = self._native.windows()
        for handle in handles:
            state = self._native.placement(handle)
            if state is None:
                continue
            current, minimized = state
            previous = self._known.get(handle)
            if previous is None:
                if self._saved is None:
                    self._save(current)
                else:
                    self._native.set_placement(handle, self._saved)
                    restored = self._native.placement(handle)
                    if restored is not None:
                        current, minimized = restored
                    else:
                        current, minimized = self._saved, False
                    if current != self._saved:
                        self._save(current)
            if minimized and previous is not None:
                current = replace(current, maximized=previous.maximized)
            self._known[handle] = current
            if previous is not None and current != previous:
                self._save(current)
        self._known = {handle: placement for handle, placement in self._known.items() if handle in handles}

    def run(self, stopped: threading.Event) -> None:
        while not stopped.is_set():
            self.check()
            stopped.wait(1.0)

    def _save(self, placement: WindowPlacement) -> None:
        self._saved = placement
        self._files.save(placement)


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", _POINT),
        ("ptMaxPosition", _POINT),
        ("rcNormalPosition", _RECT),
        ("rcDevice", _RECT),
    ]


_ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class _Windows:
    def __init__(self) -> None:
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32.EnumWindows.argtypes = [_ENUM_WINDOWS_PROC, wintypes.LPARAM]
        self._user32.EnumWindows.restype = wintypes.BOOL
        self._user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetClassNameW.restype = ctypes.c_int
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]
        self._user32.GetWindowPlacement.restype = wintypes.BOOL
        self._user32.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]
        self._user32.SetWindowPlacement.restype = wintypes.BOOL
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def windows(self) -> list[int]:
        found: list[int] = []

        def visit(handle: int, _: int) -> bool:
            if self._is_app_window(handle):
                found.append(handle)
            return True

        self._user32.EnumWindows(_ENUM_WINDOWS_PROC(visit), 0)
        return found

    def placement(self, handle: int) -> tuple[WindowPlacement, bool] | None:
        native = _WINDOWPLACEMENT()
        native.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if not self._user32.GetWindowPlacement(handle, ctypes.byref(native)):
            return None
        normal = native.rcNormalPosition
        width, height = normal.right - normal.left, normal.bottom - normal.top
        if width <= 0 or height <= 0:
            return None
        placement = WindowPlacement(
            normal.left, normal.top, width, height, maximized=native.showCmd == _SW_SHOWMAXIMIZED
        )
        return placement, native.showCmd == _SW_SHOWMINIMIZED

    def set_placement(self, handle: int, placement: WindowPlacement) -> None:
        native = _WINDOWPLACEMENT()
        native.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if not self._user32.GetWindowPlacement(handle, ctypes.byref(native)):
            _log.warning("Could not read the window before restoring it: error %s", ctypes.get_last_error())
            return
        # Windows requires the existing minimized/maximized points even when only the normal bounds change.
        native.showCmd = _SW_SHOWMAXIMIZED if placement.maximized else _SW_SHOWNORMAL
        native.rcNormalPosition = _RECT(
            placement.left,
            placement.top,
            placement.left + placement.width,
            placement.top + placement.height,
        )
        if not self._user32.SetWindowPlacement(handle, ctypes.byref(native)):
            _log.warning("Could not restore the window placement: error %s", ctypes.get_last_error())

    def _is_app_window(self, handle: int) -> bool:
        if not self._user32.IsWindowVisible(handle):
            return False
        title = ctypes.create_unicode_buffer(256)
        class_name = ctypes.create_unicode_buffer(256)
        self._user32.GetWindowTextW(handle, title, len(title))
        self._user32.GetClassNameW(handle, class_name, len(class_name))
        return (
            title.value == _WINDOW_TITLE
            and class_name.value == _EDGE_WINDOW_CLASS
            and self._is_edge_window(handle)
        )

    def _is_edge_window(self, handle: int) -> bool:
        process_id = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process = self._kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        if not process:
            return False
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self._kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                return False
            return Path(path.value).name.lower() == "msedge.exe"
        finally:
            self._kernel32.CloseHandle(process)


def open_window(url: str) -> None:
    edge = _find_edge()
    if edge is None:
        _log.warning("Edge not found; opening %s in the default browser", url)
        webbrowser.open(url)
        return
    _log.info("Opening %s in %s", url, edge)
    subprocess.Popen([str(edge), f"--app={url}"], close_fds=True)


def _find_edge() -> Path | None:
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, _APP_PATH) as key:
                path = Path(winreg.QueryValue(key, None))
        except OSError:
            continue
        if path.is_file():
            return path
    for folder in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        path = Path(os.environ.get(folder, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if path.is_absolute() and path.is_file():
            return path
    return None
