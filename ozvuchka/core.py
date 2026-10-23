"""The application core: all program state, driven by commands and read as a snapshot.

The core knows nothing about HTTP or the page. Synthesis runs on one background thread,
so commands return at once and the page sees progress through the snapshot.
"""

import itertools
import queue
import threading
from pathlib import Path
from typing import Callable

from ozvuchka.audio import Audio
from ozvuchka.voices import VoiceRegistry

SPEED = 1.0


class Core:
    def __init__(self, registry: VoiceRegistry, default_voice: str, clock: Callable[[], float], data_dir: Path):
        self._registry = registry
        self._voice = registry.voice(default_voice)
        self._clock = clock
        self._data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._phrase: dict | None = None
        self._audio: dict[str, Audio] = {}

        self._to_synthesize: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._synthesize_phrases, name="synthesis", daemon=True)
        self._worker.start()

    # ---------------------------------------------------------------- commands

    def speak(self, text: str) -> str:
        """Synthesizes a phrase in the current Voice; it replaces the previous phrase.

        Returns the phrase id, so the page can tell its phrase from an older one in the snapshot.
        """
        text = text.strip()
        if not text:
            raise ValueError("nothing to speak")
        voice = self._voice
        with self._lock:
            phrase_id = str(next(self._ids))
            self._phrase = {"id": phrase_id, "text": text, "voice": voice.key, "status": "synthesizing", "audio": None}
        self._to_synthesize.put((phrase_id, text, voice))
        return phrase_id

    def close(self) -> None:
        self._to_synthesize.put(None)
        self._worker.join(timeout=5)

    # ---------------------------------------------------------------- reading

    def snapshot(self) -> dict:
        with self._lock:
            phrase = dict(self._phrase) if self._phrase else None
        return {
            "voices": [
                {"id": v.key, "label": v.label, "available": self._registry.available(v)}
                for v in self._registry.voices()
            ],
            "voice": self._voice.key,
            "phrase": phrase,
        }

    def audio(self, audio_id: str) -> Audio | None:
        with self._lock:
            return self._audio.get(audio_id)

    # ---------------------------------------------------------------- synthesis thread

    def _synthesize_phrases(self) -> None:
        while (request := self._to_synthesize.get()) is not None:
            phrase_id, text, voice = request
            with self._lock:
                superseded = self._phrase["id"] != phrase_id
            if superseded:
                continue
            if not self._registry.available(voice):
                self._finish(phrase_id, status="failed", error=f"{voice.label}: голос недоступен")
                continue
            try:
                audio = self._registry.provider(voice).synthesize(text, voice.id, SPEED)
            except Exception as error:
                self._finish(phrase_id, status="failed", error=str(error))
                continue
            with self._lock:
                self._audio = {phrase_id: audio}  # only the current phrase is kept
            self._finish(phrase_id, status="ready", audio=phrase_id)

    def _finish(self, phrase_id: str, **changes) -> None:
        with self._lock:
            if self._phrase and self._phrase["id"] == phrase_id:
                self._phrase.update(changes)
