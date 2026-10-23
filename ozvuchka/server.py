"""Thin HTTP adapter over the core (ADR-0003): JSON commands and events, the snapshot, audio, static page.

It holds no logic of its own and listens only on 127.0.0.1.
"""

import json
import mimetypes
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ozvuchka.core import Core

WEB = Path(__file__).resolve().parent / "web"

COMMANDS: dict[str, Callable[[Core, dict[str, Any]], object]] = {
    "set_text": lambda core, body: core.set_text(str(body["text"])),
    "open_text": lambda core, body: core.open_text(str(body["id"])),
    "new_text": lambda core, body: core.new_text(),
    "play": lambda core, body: core.play(),
    "play_from": lambda core, body: core.play_from(int(body["paragraph"])),
    "pause": lambda core, body: core.pause(),
    "stop": lambda core, body: core.stop(),
    # events from the page player
    "paragraph_started": lambda core, body: core.paragraph_started(int(body["paragraph"])),
    "paragraph_finished": lambda core, body: core.paragraph_finished(int(body["paragraph"])),
}


def make_server(core: Core, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/state":
                self._send(200, "application/json", json.dumps(core.snapshot()).encode())
            elif self.path.startswith("/api/audio/"):
                audio = core.audio(self.path.removeprefix("/api/audio/"))
                if audio is None:
                    self._send_error(404, "no such audio")
                else:
                    self._send(200, audio.mime_type, audio.data)
            else:
                self._send_static(self.path.split("?", 1)[0])

        def do_POST(self) -> None:
            if self.path != "/api/command":
                return self._send_error(404, "not found")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                command = COMMANDS[body["command"]]
                result = command(core, body)
            except (ValueError, KeyError, TypeError) as error:
                return self._send_error(400, f"{type(error).__name__}: {error}")
            self._send(200, "application/json", json.dumps({"result": result}).encode())

        def _send_static(self, path: str) -> None:
            name = "index.html" if path == "/" else path.lstrip("/")
            files = {f.name: f for f in WEB.iterdir() if f.is_file()}
            if name not in files:
                return self._send_error(404, "not found")
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type.endswith("javascript"):
                content_type += "; charset=utf-8"
            self._send(200, content_type, files[name].read_bytes())

        def _send_error(self, status: int, message: str) -> None:
            self._send(status, "application/json", json.dumps({"error": message}).encode())

        def _send(self, status: int, content_type: str, data: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # the snapshot is polled twice a second; logging comes with the log ticket

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
