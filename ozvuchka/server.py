"""Thin HTTP adapter over the core (ADR-0003): JSON commands and events, the snapshot, audio and Voice samples,
the static page.

It holds no application logic, enforces the local HTTP request policy and listens only on 127.0.0.1.
"""

import json
import logging
import mimetypes
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from ozvuchka.audio import Audio
from ozvuchka.core import Core
from ozvuchka.export import ExportError, ExportResult

WEB = Path(__file__).resolve().parent / "web"
_log = logging.getLogger(__name__)

COMMANDS: dict[str, Callable[[Core, dict[str, Any]], object]] = {
    "set_text": lambda core, body: core.set_text(str(body["text"])),
    "save_text": lambda core, body: core.save_text(
        str(body["text"]), context=body["context"], sequence=body["sequence"]
    ),
    "open_text": lambda core, body: core.open_text(str(body["id"])),
    "new_text": lambda core, body: core.new_text(),
    "search_library": lambda core, body: core.search_library(str(body["query"])),
    "rename_text": lambda core, body: core.rename_text(str(body["id"]), str(body["title"])),
    "delete_text": lambda core, body: core.delete_text(str(body["id"])),
    "delete_narration": lambda core, body: core.delete_narration(
        str(body["id"]), str(body["voice"]), float(body["speed"])
    ),
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
    "page_opening": lambda core, body: core.page_opening(),
    "page_alive": lambda core, body: core.page_alive(),
    "page_closing": lambda core, body: core.page_closing(),
    "page_frozen": lambda core, body: core.page_frozen(),
}


def make_server(core: Core, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not self._local_host():
                return self._send_error(403, "unsupported Host")
            if self.path == "/api/state":
                self._send(200, "application/json", json.dumps(core.snapshot()).encode())
            elif self.path.startswith("/api/export/"):
                self._export(self.path)
            elif self.path.startswith("/api/audio/"):
                self._send_audio(core.audio(self.path.removeprefix("/api/audio/")))
            elif self.path.startswith("/api/sample/"):
                self._send_audio(core.voice_sample(unquote(self.path.removeprefix("/api/sample/"))))
            else:
                self._send_static(self.path.split("?", 1)[0])

        def do_POST(self) -> None:
            if self.path != "/api/command":
                return self._send_error(404, "not found")
            if not self._local_host():
                return self._send_error(403, "unsupported Host")
            origins = self.headers.get_all("Origin", [])
            if origins and (len(origins) != 1 or origins[0] not in allowed_origins):
                return self._send_error(403, "unsupported Origin")
            if (
                len(self.headers.get_all("Content-Type", [])) != 1
                or self.headers.get_content_type() != "application/json"
            ):
                return self._send_error(415, "commands require application/json")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                command = COMMANDS[body["command"]]
                result = command(core, body)
            except (ValueError, KeyError, TypeError) as error:
                return self._send_error(400, f"{type(error).__name__}: {error}")
            self._send(200, "application/json", json.dumps({"result": result}).encode())

        def _local_host(self) -> bool:
            hosts = self.headers.get_all("Host", [])
            return len(hosts) == 1 and hosts[0] in authorities

        def _export(self, path: str) -> None:
            try:
                request = urlsplit(path)
                query = parse_qs(request.query, keep_blank_values=True, strict_parsing=True)
                if set(query) != {"voice", "speed"} or any(len(values) != 1 for values in query.values()):
                    raise ValueError("export requires exactly one Voice and Speed")
                result = core.export_narration(
                    unquote(request.path.removeprefix("/api/export/")), query["voice"][0], float(query["speed"][0])
                )
            except ExportError as error:
                return self._send_error(409, str(error))
            except (KeyError, ValueError):
                return self._send_error(400, "Некорректный запрос экспорта MP3")
            except Exception:
                _log.exception("Could not export a Narration as MP3")
                return self._send_error(500, "Не удалось создать MP3. Попробуйте ещё раз.")
            self._send_export(result)

        def _send_export(self, result: ExportResult) -> None:
            disposition = f"attachment; filename=\"narration.mp3\"; filename*=UTF-8''{quote(result.filename, safe='')}"
            self._send(200, "audio/mpeg", result.data, {"Content-Disposition": disposition})

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

        def _send(
            self, status: int, content_type: str, data: bytes, headers: dict[str, str] | None = None
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
            if isinstance(code, int) and code >= 400:  # the snapshot is polled twice a second
                super().log_request(code, size)

        def log_message(self, format: str, *args: Any) -> None:
            _log.warning("%s: %s", self.requestline, format % args)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    authorities = {f"{host}:{server.server_port}" for host in ("127.0.0.1", "localhost")}
    if server.server_port == 80:
        authorities.update(("127.0.0.1", "localhost"))
    allowed_origins = {f"http://{host}" for host in authorities}
    return server
