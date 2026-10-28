"""Starts the program: runtime\\python.exe -m ozvuchka [--port N] [--app [--no-window]]

Озвучка.exe starts it with --app: it opens the page in the default browser and ends when the page is closed.
The page is served at once; Kokoro loads in the background. A second start on the same port opens the page of the
program already running and ends (ADR-0003).
"""

import argparse
import ctypes
import logging
import os
import platform
import threading
import time
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from ozvuchka.core import Core
from ozvuchka.kokoro import DEFAULT_VOICE, KokoroProvider
from ozvuchka.log import start_log
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry

ROOT = Path(__file__).resolve().parent.parent  # the program folder (ADR-0001)
_log = logging.getLogger("ozvuchka")
_RUNNING_TIMEOUT = 30.0  # seconds for the program already running to serve its page or end
_WAIT_OBJECT_0, _WAIT_ABANDONED = 0x0, 0x80  # the mutex is ours; or ours since its owner ended


def main() -> None:
    parser = argparse.ArgumentParser(prog="ozvuchka")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--app", action="store_true", help="open the page and end when it is closed")
    parser.add_argument("--no-window", action="store_true", help="with --app: do not open the page (smoke test)")
    args = parser.parse_args()

    os.chdir(ROOT)  # as from Озвучка.exe; eSpeak NG needs a path relative to it (kokoro.py)
    start_log(ROOT / "data")
    version_file = ROOT / "version.txt"  # written by the release build
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "dev"
    open_page = args.app and not args.no_window
    url = f"http://127.0.0.1:{args.port}"
    # an error is logged by start_log's hook
    if _first_on_port(args.port, url):
        _log.info("Ozvuchka %s started in %s", version, ROOT)
        _run(args.port, args.app, open_page)
        _log.info("Ozvuchka stopped")
    else:
        _log.info("Ozvuchka is already running at %s; opening its page", url)
        if open_page:
            webbrowser.open(url)


def _first_on_port(port: int, url: str) -> bool:
    """Whether this is the one Ozvuchka on this port, which it stays until its process ends; False once the one
    already running serves its page. A named mutex, so two starts at once cannot both win and nothing heavy is
    loaded before it is known; a start while the other one is ending takes over after it."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, f"Local\\Ozvuchka-{port}")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    deadline = time.monotonic() + _RUNNING_TIMEOUT
    # The handle is left open and the mutex stays owned by this, the main, thread until the process ends.
    while kernel32.WaitForSingleObject(handle, 0) not in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
        if _serves_page(url):
            return False
        if time.monotonic() > deadline:
            raise RuntimeError(f"Ozvuchka on port {port} neither serves its page nor ends")
        kernel32.WaitForSingleObject(handle, 500)  # its result is seen by the check above
    return True


def _serves_page(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/state", timeout=5):
            return True
    except OSError:
        return False


def _run(port: int, app: bool, open_page: bool) -> None:
    core = Core(
        VoiceRegistry([KokoroProvider(ROOT / "models" / "kokoro")]),
        DEFAULT_VOICE,
        clock=time.monotonic,
        data_dir=ROOT / "data",
        computer=platform.node(),  # the Synthesis speed is remembered for each computer
    )
    server = make_server(core, port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    _log.info("Serving %s", url)
    if app:
        threading.Thread(target=_end_when_closed, args=(core, server), name="window", daemon=True).start()
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        core.close()


def _end_when_closed(core: Core, server: ThreadingHTTPServer) -> None:
    while not core.page_gone():
        time.sleep(1)
    _log.info("The window is closed")
    server.shutdown()


if __name__ == "__main__":
    main()
