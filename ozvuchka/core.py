"""The application core: all program state, driven by commands and read as a snapshot.

The core knows nothing about HTTP or the page. Synthesis runs on one background thread,
one piece at a time, so commands return at once and the page sees progress through the snapshot.
"""

import hashlib
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ozvuchka.audio import Audio
from ozvuchka.library import LibraryFiles, SavedText
from ozvuchka.text import Paragraph, paragraphs
from ozvuchka.voices import VoiceRegistry

SPEED = 1.0
_TITLE_WORDS = 5  # a Text's title in the Library is its first words


class Core:
    def __init__(self, registry: VoiceRegistry, default_voice: str, clock: Callable[[], float], data_dir: Path):
        self._registry = registry
        self._voice = registry.voice(default_voice)
        self._clock = clock
        self._files = LibraryFiles(data_dir)

        self._lock = threading.Lock()
        self._work = threading.Condition(self._lock)  # wakes the synthesis thread
        self._closed = False
        self._library: list[SavedText] = []  # most recently used first
        self._library_error: str | None = None  # why the Library could not be read or saved
        self._library_readable = True  # an unreadable Library file is never overwritten
        try:
            self._library = self._files.texts()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self._library_readable = False
            self._library_error = f"Не удалось прочитать Библиотеку: {error}"
        self._text_id: str | None = None  # the current Text's place in the Library; None until it is saved
        self._text: str | None = None
        self._paragraphs: list[Paragraph] = []
        self._play_pressed = False  # Play asked for the current Text to be synthesized
        # A piece's audio is saved in the Library; only one that could not be saved is kept in memory.
        self._saved_pieces = self._files.pieces()
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
        """Puts this in the current Text and saves it in the Library; the same Text again (the page after F5)
        changes nothing. Pieces that stay the same keep their Narration."""
        with self._work:
            if text == self._text:
                return
            self._show(text)
            if self._paragraphs:
                self._text_id = self._text_id or uuid.uuid4().hex[:12]
                self._move_to_front(SavedText(self._text_id, text))

    def open_text(self, text_id: str) -> None:
        """Makes a Text from the Library the current one."""
        with self._work:
            saved = next((t for t in self._library if t.id == text_id), None)
            if saved is None:
                raise ValueError(f"no text {text_id} in the library")
            if text_id != self._text_id or saved.content != self._text:
                self._text_id = text_id
                self._show(saved.content)
            self._move_to_front(saved)

    def new_text(self) -> None:
        """Leaves the current Text in the Library; the next set_text starts a new one."""
        with self._work:
            self._text_id = None
            self._show(None)

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

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            text = None if self._text is None else {
                "id": self._text_id,
                "content": self._text,
                "paragraphs": [self._paragraph_state(p) for p in self._paragraphs],
            }
            playback = {
                "state": self._state,
                "paragraph": self._paragraph,
                "next": None if self._paragraph is None else self._readable_after(self._paragraph),
            }
            library = [{"id": t.id, "title": _title(t.content)} for t in self._library]
            library_error = self._library_error
        return {
            "voices": [
                {"id": v.key, "label": v.label, "available": self._registry.available(v)}
                for v in self._registry.voices()
            ],
            "voice": self._voice.key,
            "library": library,
            "library_error": library_error,
            "text": text,
            "playback": playback,
        }

    def audio(self, audio_id: str) -> Audio | None:
        with self._lock:
            if audio_id in self._audio:
                return self._audio[audio_id]
            saved = audio_id in self._saved_pieces
        try:
            return self._files.piece(audio_id) if saved else None
        except OSError:
            return None

    def _show(self, text: str | None) -> None:
        self._text = text
        self._paragraphs = [] if text is None else paragraphs(text)
        self._play_pressed = False
        self._state, self._paragraph = "stopped", None
        self._failed.clear()

    def _move_to_front(self, text: SavedText) -> None:
        """Saves the Library with this Text as the most recently used one."""
        self._library = [text] + [t for t in self._library if t.id != text.id]
        if not self._library_readable:
            return
        try:
            self._files.save_texts(self._library)
            self._library_error = None
        except OSError as error:
            self._library_error = f"Не удалось сохранить Библиотеку: {error}"

    def _readable(self, index: int) -> bool:
        return 0 <= index < len(self._paragraphs) and not self._paragraphs[index].skipped

    def _readable_after(self, index: int) -> int | None:
        """The next Paragraph to play after this one: Skipped paragraphs are passed over."""
        return next((i for i in range(index + 1, len(self._paragraphs)) if self._readable(i)), None)

    def _ready(self, audio_id: str) -> bool:
        return audio_id in self._saved_pieces or audio_id in self._audio

    def _paragraph_state(self, paragraph: Paragraph) -> dict[str, Any]:
        state: dict[str, Any] = {"text": paragraph.text, "audio": None}
        ids = self._audio_ids(paragraph)
        if paragraph.skipped:
            state["status"] = "skipped"
        elif errors := [self._failed[i] for i in ids if i in self._failed]:
            state.update(status="failed", error=errors[0])
        elif all(self._ready(i) for i in ids):
            state.update(status="ready", audio=ids)
        elif self._synthesizing in ids or any(self._ready(i) for i in ids):
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
            for audio_id, piece in zip(self._audio_ids(paragraph), paragraph.pieces, strict=True):
                if not self._ready(audio_id) and audio_id not in self._failed:
                    return audio_id, piece
        return None

    def _synthesize_pieces(self) -> None:
        while True:
            with self._work:
                piece = self._next_piece()
                while not self._closed and piece is None:
                    self._work.wait()
                    piece = self._next_piece()
                if self._closed or piece is None:
                    return
                audio_id, text = piece
                voice = self._voice
                self._synthesizing = audio_id
            result: Audio | str  # the audio, or why there is none
            try:
                if not self._registry.available(voice):
                    raise RuntimeError(f"{voice.label}: голос недоступен")
                result = self._registry.provider(voice).synthesize(text, voice.id, SPEED)
            except Exception as error:
                result = str(error)
            save_error = None
            if isinstance(result, Audio):
                try:
                    self._files.save_piece(audio_id, result)
                except OSError as error:
                    save_error = f"Не удалось сохранить озвучку: {error}"
            with self._lock:
                self._synthesizing = None
                if not isinstance(result, Audio):
                    self._failed[audio_id] = result
                elif save_error is None:
                    self._saved_pieces.add(audio_id)
                else:
                    self._audio[audio_id] = result  # it still plays until the program is closed
                    self._library_error = save_error


def _title(content: str) -> str:
    words = content.split()
    if len(words) <= _TITLE_WORDS:
        return " ".join(words)
    return " ".join(words[:_TITLE_WORDS]).rstrip(",;:—–-") + "…"
