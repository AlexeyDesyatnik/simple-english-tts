"""Serve the real UI with an isolated disposable Library for the experiment-2 design review.

Run with runtime/python.exe -X utf8 tools/ui_design_preview.py; Ctrl+C closes the server
and removes only its temporary Library. The default fake produces silence; --real-voice uses real Kokoro speech.
"""

import argparse
import tempfile
import threading
import time
from pathlib import Path

from ozvuchka.audio import Audio
from ozvuchka.core import Core
from ozvuchka.kokoro import DEFAULT_VOICE, KokoroProvider
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceProvider, VoiceRegistry, check_cancelled
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


class _PreviewVoiceProvider(FakeVoiceProvider):
    """Pace the existing fake for visible loading and queue checks, without changing Core."""

    def __init__(self, load_seconds: float, piece_seconds: float, unavailable: bool, fail_text: str) -> None:
        super().__init__(loading=load_seconds > 0, available=not unavailable)
        self._load_seconds = load_seconds
        self._piece_seconds = piece_seconds
        self._fail_text = fail_text

    def load(self) -> None:
        time.sleep(self._load_seconds)
        self.finish_loading()
        super().load()

    def synthesize(self, text: str, voice: str, speed: float, cancel: threading.Event | None = None) -> Audio:
        if cancel is None:
            time.sleep(self._piece_seconds)
        else:
            cancel.wait(self._piece_seconds)
        check_cancelled(cancel)
        if self._fail_text and self._fail_text in text:
            raise RuntimeError("Тестовая ошибка подготовки абзаца")
        return super().synthesize(text, voice, speed, cancel)


def _wait_until_ready(core: Core, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while core.snapshot()["queue"]:
        if time.monotonic() > deadline:
            raise TimeoutError("Preview Narrations did not become ready")
        time.sleep(0.05)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--texts", type=int, choices=(0, 1, 20), default=20)
    parser.add_argument("--long-title", action="store_true", help="Seed a multi-line title for layout checks")
    parser.add_argument("--load-seconds", type=float, default=0, help="Show initial Voice loading")
    parser.add_argument("--piece-seconds", type=float, default=0, help="Delay each fake synthesis piece")
    parser.add_argument("--unavailable", action="store_true", help="Show unavailable Voices")
    parser.add_argument("--no-ready", action="store_true", help="Skip seeding ready Narrations")
    parser.add_argument("--fail-text", default="", help="Fail synthesis containing this text (use with --no-ready)")
    parser.add_argument(
        "--real-voice", action="store_true", help="Use installed Kokoro for audible review",
    )
    args = parser.parse_args()
    if args.real_voice and (args.load_seconds or args.piece_seconds or args.unavailable or args.fail_text):
        parser.error("--real-voice cannot be combined with fake loading, pacing, availability or failure options")
    root = Path(__file__).resolve().parents[1]
    provider: VoiceProvider
    if args.real_voice:
        provider = KokoroProvider(root / "models" / "kokoro")
        alice, george = DEFAULT_VOICE, "kokoro:bm_george"
    else:
        provider = _PreviewVoiceProvider(args.load_seconds, args.piece_seconds, args.unavailable, args.fail_text)
        alice, george = "fake:alice", "fake:george"

    preview_root = Path(__file__).resolve().parents[1] / ".cache" / "ui-design-preview"
    preview_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="issue-28-", dir=preview_root) as temporary:
        core = Core(
            VoiceRegistry([provider]), alice, clock=time.monotonic,
            data_dir=Path(temporary), computer="isolated-design-review",
        )
        try:
            for index in range(args.texts):
                core.new_text()
                core.set_text(f"Reading practice number {index + 1}.\nWhere would you like to travel?")
            if args.texts:
                core.set_text(_TEXT)
                text_id = str(core.snapshot()["text"]["id"])
                title = "A Saturday discovery — история о прогулке по старому городу"
                if args.long_title:
                    title = (
                        "A Saturday discovery — an English reading activity about exploring the old town, "
                        "finding unexpected places, sharing observations with classmates and writing "
                        "a story together after the lesson"
                    )
                core.rename_text(text_id, title)
                if not args.no_ready:
                    core.enqueue()
                    _wait_until_ready(core, 300 if args.real_voice else 20)
                    core.set_voice(george)
                    core.enqueue()
                    _wait_until_ready(core, 300 if args.real_voice else 20)
                    core.set_voice(alice)
            server = make_server(core, port=args.port)
            print(f"Isolated design preview: http://127.0.0.1:{server.server_address[1]}", flush=True)
            print(f"Disposable Library: {temporary}", flush=True)
            print(f"Voice provider: {provider.id}", flush=True)
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
