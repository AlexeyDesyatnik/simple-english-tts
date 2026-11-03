"""Serve the real UI with an isolated disposable Library for the experiment-2 design review.

Run with runtime/python.exe -X utf8 tools/ui_design_preview.py; Ctrl+C closes the server
and removes only its temporary Library. FakeVoiceProvider produces silence, not real speech.
"""

import argparse
import tempfile
import time
from pathlib import Path

from ozvuchka.core import Core
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeVoiceProvider

_TEXT = "\n".join([
    "Прочитайте текст и обсудите вопросы.",
    "On Saturday morning, Emma and her brother visited a small bookshop near the river.",
    "The owner showed them a map of the town as it was a hundred years ago.",
    "They decided to follow the old streets and look for places that had not changed.",
    "Behind the station, they found a quiet garden with a tall apple tree.",
    "Emma took a photograph and wrote a short story about their unexpected discovery.",
    "What would you like to discover in your own town?",
])


def _wait_until_ready(core: Core) -> None:
    deadline = time.monotonic() + 20
    while core.snapshot()["queue"]:
        if time.monotonic() > deadline:
            raise TimeoutError("Preview Narrations did not become ready")
        time.sleep(0.05)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--texts", type=int, choices=(0, 1, 20), default=20)
    args = parser.parse_args()
    preview_root = Path(__file__).resolve().parents[1] / ".cache" / "ui-design-preview"
    preview_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="issue-28-", dir=preview_root) as temporary:
        core = Core(
            VoiceRegistry([FakeVoiceProvider()]), "fake:alice", clock=time.monotonic,
            data_dir=Path(temporary), computer="isolated-design-review",
        )
        try:
            for index in range(args.texts):
                core.new_text()
                core.set_text(f"Reading practice number {index + 1}.\nWhere would you like to travel?")
            if args.texts:
                core.set_text(_TEXT)
                text_id = str(core.snapshot()["text"]["id"])
                core.rename_text(text_id, "A Saturday discovery — история о прогулке по старому городу")
                core.enqueue()
                _wait_until_ready(core)
                core.set_voice("fake:george")
                core.enqueue()
                _wait_until_ready(core)
                core.set_voice("fake:alice")
            server = make_server(core, port=args.port)
            print(f"Isolated design preview: http://127.0.0.1:{server.server_address[1]}", flush=True)
            print(f"Disposable Library: {temporary}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        finally:
            core.close()


if __name__ == "__main__":
    main()
