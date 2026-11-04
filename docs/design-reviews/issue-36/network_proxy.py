"""Optional local delay proxy for stage 9 acceptance, using only a disposable preview.

Run from the repository root. This is review instrumentation, not an application endpoint.
"""

import argparse
import http.client
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18737)
    parser.add_argument("--target-port", type=int, default=18736)
    parser.add_argument("--config", type=Path, default=Path(".cache/issue36-network.json"))
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def _forward(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            settings = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config.exists() else {}
            command = json.loads(body) if body else {}
            delayed = command.get("command") == "save_text" and command.get("sequence") == settings.get("sequence")
            if delayed and settings.get("mode") == "request":
                print("Holding request", command["sequence"], flush=True)
                time.sleep(settings.get("seconds", 12))
            connection = http.client.HTTPConnection("127.0.0.1", args.target_port)
            try:
                connection.request(self.command, self.path, body, {"Content-Type": "application/json"})
                response = connection.getresponse()
                data = response.read()
                if command.get("command") == "save_text":
                    print(command["sequence"], data.decode(), flush=True)
                if delayed and settings.get("mode") == "response":
                    time.sleep(settings.get("seconds", 12))
                self.send_response(response.status)
                self.send_header("Content-Type", response.getheader("Content-Type") or "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # The departing page need not receive its response.
            finally:
                connection.close()

        do_GET = _forward
        do_POST = _forward

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Review proxy: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
