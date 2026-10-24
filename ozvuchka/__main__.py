"""Starts the program: runtime\\python.exe -m ozvuchka [--port N] [--app [--no-window]]

Озвучка.exe starts it with --app: it opens its own window and ends when the window is closed.
"""

import argparse
import logging
import os
import platform
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

from ozvuchka.core import Core
from ozvuchka.kokoro import DEFAULT_VOICE, KokoroProvider
from ozvuchka.log import start_log
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry
from ozvuchka.window import open_window

ROOT = Path(__file__).resolve().parent.parent  # the program folder (ADR-0001)
_log = logging.getLogger("ozvuchka")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ozvuchka")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--app", action="store_true", help="open the window and end when it is closed")
    parser.add_argument("--no-window", action="store_true", help="with --app: do not open the window (smoke test)")
    args = parser.parse_args()

    os.chdir(ROOT)  # as from Озвучка.exe; eSpeak NG needs a path relative to it (kokoro.py)
    start_log(ROOT / "data")
    version_file = ROOT / "version.txt"  # written by the release build
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "dev"
    _log.info("Ozvuchka %s started in %s", version, ROOT)
    _run(args.port, args.app, open_page=args.app and not args.no_window)  # an error is logged by start_log's hook
    _log.info("Ozvuchka stopped")


def _run(port: int, app: bool, open_page: bool) -> None:
    kokoro = KokoroProvider(ROOT / "models" / "kokoro")
    _log.info("Loading Kokoro…")
    started = time.monotonic()
    kokoro.load()
    _log.info("Kokoro loaded in %.1f s", time.monotonic() - started)
    core = Core(
        VoiceRegistry([kokoro]),
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
        open_window(url)
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
