"""Selects the per-port process lock and applies the common running-instance handshake."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Protocol

_RUNNING_TIMEOUT = 30.0  # seconds for the program already running to serve its page or end


class PortLock(Protocol):
    def acquire(self) -> bool: ...

    def close(self) -> None: ...


def claim_port(port: int, url: str, open_page: bool, data_dir: Path) -> PortLock | None:
    """Return the owned process-lifetime lock, or None once the running instance accepts its page."""
    if sys.platform == "win32":
        from ozvuchka.instance_windows import WindowsPortLock

        lock: PortLock = WindowsPortLock(port)
    else:
        from ozvuchka.instance_posix import PosixPortLock

        lock = PosixPortLock(port, data_dir)
    if lock.acquire():
        return lock
    deadline = time.monotonic() + _RUNNING_TIMEOUT
    try:
        while True:
            already_running = _page_opening(url) if open_page else _serves_page(url)
            if already_running:
                lock.close()
                return None
            if time.monotonic() > deadline:
                raise RuntimeError(f"Ozvuchka on port {port} neither serves its page nor ends")
            time.sleep(0.5)
            if lock.acquire():
                return lock
    except Exception:
        lock.close()
        raise


def _serves_page(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/state", timeout=5):
            return True
    except OSError:
        return False


def _page_opening(url: str) -> bool:
    request = urllib.request.Request(
        url + "/api/command",
        data=b'{"command":"page_opening"}',
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)["result"] is True
    except OSError:
        return False
