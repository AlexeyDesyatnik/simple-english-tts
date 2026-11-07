"""Opens the local page and, on Windows, remembers the Edge app-window placement (ADR-0003).

Linux and Windows without Edge use the default browser; Linux has no native placement monitor.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import threading
import webbrowser
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

_log = logging.getLogger(__name__)
_FORMAT_VERSION = 1


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
        if native is None:
            from ozvuchka.window_windows import Windows

            native = Windows()
        self._native = native
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


def open_window(url: str) -> None:
    if sys.platform == "win32":
        from ozvuchka.window_windows import open_windows_window

        open_windows_window(url)
    else:
        open_default_browser(url)


def open_default_browser(url: str) -> None:
    try:
        opened = webbrowser.open(url)
    except Exception:
        _log.warning("Could not open %s in the default browser", url, exc_info=True)
        return
    if not opened:
        _log.warning("Could not open %s in the default browser", url)
