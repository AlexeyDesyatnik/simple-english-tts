"""The application core: all program state, driven by commands and read as a snapshot.

The core knows nothing about HTTP or the page. Synthesis runs on one background thread,
one piece at a time, so commands return at once and the page sees progress through the snapshot.
"""

import hashlib
import threading
from pathlib import Path
from typing import Callable

from ozvuchka.audio import Audio
from ozvuchka.text import Paragraph, paragraphs
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
        self._work = threading.Condition(self._lock)  # wakes the synthesis thread
        self._closed = False
        self._text: str | None = None
        self._paragraphs: list[Paragraph] = []
        self._play_pressed = False  # Play asked for the current Text to be synthesized
        # audio id -> audio of one piece; kept while the program runs, so going back to a Text plays at once
        self._audio: dict[str, Audio] = {}
        self._failed: dict[str, str] = {}  # audio id -> why its piece could not be synthesized
        self._synthesizing: str | None = None
        # The playback position: the page plays, but the core decides what (ADR-0003).
        self._state = "stopped"  # "playing" | "paused" | "stopped"
        self._paragraph: int | None = None

        self._worker = threading.Thread(target=self._synthesize_pieces, name="synthesis", daemon=True)
        self._worker.start()

    # ---------------------------------------------------------------- commands

    def set_text(self, text: str) -> None:
        """Makes this the current Text; the same Text again (the page after F5) changes nothing."""
        with self._work:
            if text == self._text:
                return
            self._text = text
            self._paragraphs = paragraphs(text)
            self._play_pressed = False
            self._state, self._paragraph = "stopped", None
            self._failed.clear()

    def play(self) -> None:
        with self._work:
            if self._text is None:
                raise ValueError("no text to play")
            self._play_pressed = True
            self._failed.clear()  # Play tries again what could not be synthesized
            self._work.notify()
            if self._state == "stopped":
                self._paragraph = self._readable_after(-1)
                if self._paragraph is not None:
                    self._state = "playing"
            elif self._state == "paused":
                self._state = "playing"

    def pause(self) -> None:
        with self._lock:
            if self._state == "playing":
                self._state = "paused"

    def stop(self) -> None:
        with self._lock:
            self._state, self._paragraph = "stopped", None

    # ---------------------------------------------------------------- events from the page player

    def paragraph_started(self, index: int) -> None:
        with self._lock:
            if self._state == "playing" and self._readable(index):
                self._paragraph = index

    def paragraph_finished(self, index: int) -> None:
        with self._lock:
            if self._state == "playing" and index == self._paragraph:
                self._paragraph = self._readable_after(index)
                if self._paragraph is None:
                    self._state = "stopped"  # the end of the Text

    def close(self) -> None:
        with self._work:
            self._closed = True
            self._work.notify()
        self._worker.join(timeout=5)

    # ---------------------------------------------------------------- reading

    def snapshot(self) -> dict:
        with self._lock:
            text = None if self._text is None else {
                "content": self._text,
                "paragraphs": [self._paragraph_state(p) for p in self._paragraphs],
            }
            playback = {
                "state": self._state,
                "paragraph": self._paragraph,
                "next": None if self._paragraph is None else self._readable_after(self._paragraph),
            }
        return {
            "voices": [
                {"id": v.key, "label": v.label, "available": self._registry.available(v)}
                for v in self._registry.voices()
            ],
            "voice": self._voice.key,
            "text": text,
            "playback": playback,
        }

    def audio(self, audio_id: str) -> Audio | None:
        with self._lock:
            return self._audio.get(audio_id)

    def _readable(self, index: int) -> bool:
        return 0 <= index < len(self._paragraphs) and not self._paragraphs[index].skipped

    def _readable_after(self, index: int) -> int | None:
        """The next Paragraph to play after this one: Skipped paragraphs are passed over."""
        return next((i for i in range(index + 1, len(self._paragraphs)) if self._readable(i)), None)

    def _paragraph_state(self, paragraph: Paragraph) -> dict:
        state = {"text": paragraph.text, "audio": None}
        ids = self._audio_ids(paragraph)
        if paragraph.skipped:
            state["status"] = "skipped"
        elif errors := [self._failed[i] for i in ids if i in self._failed]:
            state.update(status="failed", error=errors[0])
        elif all(i in self._audio for i in ids):
            state.update(status="ready", audio=ids)
        elif self._synthesizing in ids or any(i in self._audio for i in ids):
            state["status"] = "synthesizing"
        else:
            state["status"] = "waiting"
        return state

    # ---------------------------------------------------------------- synthesis thread

    def _audio_ids(self, paragraph: Paragraph) -> list[str]:
        """A piece's audio is the same for the same prepared text, Voice and Speed."""
        return [
            hashlib.sha1(f"{self._voice.key}|{SPEED}|{piece}".encode()).hexdigest()[:16] for piece in paragraph.pieces
        ]

    def _next_piece(self) -> tuple[str, str] | None:
        if not self._play_pressed:
            return None
        for paragraph in self._paragraphs:
            for audio_id, piece in zip(self._audio_ids(paragraph), paragraph.pieces):
                if audio_id not in self._audio and audio_id not in self._failed:
                    return audio_id, piece
        return None

    def _synthesize_pieces(self) -> None:
        while True:
            with self._work:
                while not self._closed and (piece := self._next_piece()) is None:
                    self._work.wait()
                if self._closed:
                    return
                audio_id, text = piece
                voice = self._voice
                self._synthesizing = audio_id
            audio = error = None
            try:
                if not self._registry.available(voice):
                    raise RuntimeError(f"{voice.label}: голос недоступен")
                audio = self._registry.provider(voice).synthesize(text, voice.id, SPEED)
            except Exception as e:
                error = str(e)
            with self._lock:
                self._synthesizing = None
                if audio is not None:
                    self._audio[audio_id] = audio
                else:
                    self._failed[audio_id] = error
