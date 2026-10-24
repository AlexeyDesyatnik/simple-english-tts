"""Thin HTTP adapter over the core (ADR-0003): JSON commands and events, the snapshot, audio and Voice samples,
the static page.

It holds no logic of its own and listens only on 127.0.0.1.
"""

import json
import logging
import mimetypes
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from ozvuchka.audio import Audio
from ozvuchka.core import Core

WEB = Path(__file__).resolve().parent / "web"
_log = logging.getLogger(__name__)

COMMANDS: dict[str, Callable[[Core, dict[str, Any]], object]] = {
    "set_text": lambda core, body: core.set_text(str(body["text"])),
    "open_text": lambda core, body: core.open_text(str(body["id"])),
    "new_text": lambda core, body: core.new_text(),
    "set_voice": lambda core, body: core.set_voice(str(body["voice"])),
    "set_speed": lambda core, body: core.set_speed(float(body["speed"])),
    "bigger_text": lambda core, body: core.bigger_text(),
    "smaller_text": lambda core, body: core.smaller_text(),
    "enqueue": lambda core, body: core.enqueue(),
    "cancel": lambda core, body: core.cancel(str(body["narration"])),
    "play": lambda core, body: core.play(),
    "play_from": lambda core, body: core.play_from(int(body["paragraph"])),
    "next_paragraph": lambda core, body: core.next_paragraph(),
    "previous_paragraph": lambda core, body: core.previous_paragraph(),
    "repeat_paragraph": lambda core, body: core.repeat_paragraph(),
    "pause": lambda core, body: core.pause(),
    "stop": lambda core, body: core.stop(),
    # events from the page player
    "paragraph_started": lambda core, body: core.paragraph_started(int(body["paragraph"])),
    "paragraph_finished": lambda core, body: core.paragraph_finished(int(body["paragraph"])),
    # the page's heartbeat
    "page_alive": lambda core, body: core.page_alive(),
    "page_closing": lambda core, body: core.page_closing(),
    "page_frozen": lambda core, body: core.page_frozen(),
}


def make_server(core: Core, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/state":
                self._send(200, "application/json", json.dumps(core.snapshot()).encode())
            elif self.path.startswith("/api/audio/"):
                self._send_audio(core.audio(self.path.removeprefix("/api/audio/")))
            elif self.path.startswith("/api/sample/"):
                self._send_audio(core.voice_sample(unquote(self.path.removeprefix("/api/sample/"))))
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

        def _send_audio(self, audio: Audio | None) -> None:
            if audio is None:
                self._send_error(404, "no such audio")
            else:
                self._send(200, audio.mime_type, audio.data)

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

        def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
            if isinstance(code, int) and code >= 400:  # the snapshot is polled twice a second
                super().log_request(code, size)

        def log_message(self, format: str, *args: Any) -> None:
            _log.warning("%s: %s", self.requestline, format % args)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
