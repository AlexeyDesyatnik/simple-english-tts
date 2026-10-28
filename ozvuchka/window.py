"""Opens the program's window: the page in an Edge app window, msedge --app=<url> (ADR-0003).

Without Edge the page opens in the default browser, so the teacher still gets the program.
"""

import logging
import os
import subprocess
import webbrowser
import winreg
from pathlib import Path

_log = logging.getLogger(__name__)
_APP_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"


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
