"""Windows-only Edge discovery, app-window opening and native placement access."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Any

from ozvuchka.window import WindowPlacement, open_default_browser

_log = logging.getLogger(__name__)
_APP_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
_WINDOW_TITLE = "Озвучка"
_EDGE_WINDOW_CLASS = "Chrome_WidgetWin_1"
_SW_SHOWNORMAL = 1
_SW_SHOWMINIMIZED = 2
_SW_SHOWMAXIMIZED = 3
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ctypes: Any = ctypes  # Win32-only ctypes names are absent from POSIX type stubs.
_winreg: Any = winreg


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


_ENUM_WINDOWS_PROC = _ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class Windows:
    def __init__(self) -> None:
        self._user32 = _ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = _ctypes.WinDLL("kernel32", use_last_error=True)
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
            _log.warning("Could not read the window before restoring it: error %s", _ctypes.get_last_error())
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
            _log.warning("Could not restore the window placement: error %s", _ctypes.get_last_error())

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


def open_windows_window(url: str) -> None:
    edge = _find_edge()
    if edge is None:
        _log.warning("Edge not found; opening %s in the default browser", url)
        open_default_browser(url)
        return
    _log.info("Opening %s in %s", url, edge)
    subprocess.Popen([str(edge), f"--app={url}"], close_fds=True)


def _find_edge() -> Path | None:
    for root in (_winreg.HKEY_CURRENT_USER, _winreg.HKEY_LOCAL_MACHINE):
        try:
            with _winreg.OpenKey(root, _APP_PATH) as key:
                path = Path(_winreg.QueryValue(key, None))
        except OSError:
            continue
        if path.is_file():
            return path
    for folder in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        path = Path(os.environ.get(folder, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if path.is_absolute() and path.is_file():
            return path
    return None
