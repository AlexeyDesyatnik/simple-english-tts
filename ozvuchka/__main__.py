"""Starts the program with the platform runtime: python -m ozvuchka [--port N] [--app [--no-window]].

The Windows launcher starts it with --app. Linux uses the same flag from its development runtime. The page
is served at once; Kokoro loads in the background. A second start on the same port opens the running page
and ends (ADR-0003).
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

from ozvuchka.instance import claim_port
from ozvuchka.log import start_log
from ozvuchka.window import WindowMonitor, open_window

if TYPE_CHECKING:
    from ozvuchka.core import Core

ROOT = Path(__file__).resolve().parent.parent  # the program folder (ADR-0001)
_log = logging.getLogger("ozvuchka")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ozvuchka")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--app", action="store_true", help="open the window and end when it is closed")
    parser.add_argument("--no-window", action="store_true", help="with --app: do not open the window (smoke test)")
    args = parser.parse_args()

    start_log(ROOT / "data", console=os.environ.get("OZVUCHKA_LAUNCHER") != "1")
    os.chdir(ROOT)  # eSpeak NG needs a path relative to the program folder (kokoro.py)
    version_file = ROOT / "version.txt"  # written by the release build
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "dev"
    open_page = args.app and not args.no_window
    url = f"http://127.0.0.1:{args.port}"
    # an error is logged by start_log's hook
    port_lock = claim_port(args.port, url, open_page, ROOT / "data")
    if port_lock is not None:
        _log.info("Ozvuchka %s started in %s", version, ROOT)
        try:
            _run(args.port, args.app, open_page)
        finally:
            port_lock.close()
        _log.info("Ozvuchka stopped")
    else:
        _log.info("Ozvuchka is already running at %s; opening its window", url)
        if open_page:
            open_window(url)


def _run(port: int, app: bool, open_page: bool) -> None:
    # Native dependencies must load after diagnostics and only in the first instance.
    from ozvuchka.core import Core
    from ozvuchka.kokoro import DEFAULT_VOICE, KokoroProvider
    from ozvuchka.server import make_server
    from ozvuchka.voices import VoiceRegistry

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
    window_stopped = threading.Event()
    if app:
        threading.Thread(target=_end_when_closed, args=(core, server), name="window", daemon=True).start()
        if sys.platform == "win32":
            monitor = WindowMonitor(ROOT / "data")
            threading.Thread(target=monitor.run, args=(window_stopped,), name="window-placement", daemon=True).start()
    if open_page:
        open_window(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        window_stopped.set()
        server.server_close()
        core.close()


def _end_when_closed(core: Core, server: ThreadingHTTPServer) -> None:
    while not core.page_gone():
        time.sleep(1)
    _log.info("The window is closed")
    server.shutdown()


if __name__ == "__main__":
    main()
