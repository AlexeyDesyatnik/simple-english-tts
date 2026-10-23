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
from ozvuchka.scheduling import PlannedPiece, SpeedRecords, measured, start_delay
from ozvuchka.text import Paragraph, paragraphs
from ozvuchka.voices import VoiceRegistry

SPEED = 1.0
_TITLE_WORDS = 5  # a Text's title in the Library is its first words


class Core:
    def __init__(
        self,
        registry: VoiceRegistry,
        default_voice: str,
        clock: Callable[[], float],
        data_dir: Path,
        computer: str,
    ):
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
        self._durations: dict[str, float] = {}  # audio id -> seconds, for the pieces synthesized since the start
        self._computer = computer
        self._speeds = SpeedRecords(data_dir)
        self._speed = self._speeds.speed(computer)
        self._synthesizing: str | None = None
        self._synthesizing_since = 0.0
        self._synthesizing_length = 0  # characters
        # The playback position: the page plays, but the core decides what (ADR-0003).
        # "waiting" is after Play, until the Narration can play through without stopping to wait.
        self._state = "stopped"  # "waiting" | "playing" | "paused" | "stopped"
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
            if self._state == "stopped":
                self._paragraph = self._readable_after(-1)
                if self._paragraph is not None:
                    self._state = "waiting"
            elif self._state == "paused":
                self._state = "waiting"
            self._press_play()

    def play_from(self, index: int) -> None:
        """Plays from this Paragraph, synthesizing it and the ones after it first."""
        with self._work:
            if not self._readable(index):
                raise ValueError(f"paragraph {index} cannot be played")
            self._state, self._paragraph = "waiting", index
            self._press_play()

    def _press_play(self) -> None:
        self._play_pressed = True
        self._failed.clear()  # Play tries again what could not be synthesized
        self._work.notify()
        self._start_when_safe()

    def pause(self) -> None:
        with self._lock:
            if self._state in ("waiting", "playing"):
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
            self._start_when_safe()
            text = None if self._text is None else {
                "id": self._text_id,
                "content": self._text,
                "paragraphs": [self._paragraph_state(p) for p in self._paragraphs],
            }
            playback = {
                "state": self._state,
                "paragraph": self._paragraph,
                "next": None if self._paragraph is None else self._readable_after(self._paragraph),
                "start_delay": self._start_delay() if self._state == "waiting" else None,
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

    def _start_when_safe(self) -> None:
        """Starts playback once the Narration can play through without stopping to wait for synthesis."""
        if self._state != "waiting" or self._paragraph is None:
            return
        current = self._paragraphs[self._paragraph]
        if all(self._ready(i) for i in self._audio_ids(current)) and self._start_delay() == 0:
            self._state = "playing"

    def _start_delay(self) -> float | None:
        """Seconds until playback from the current Paragraph can start; None until the Synthesis speed is known."""
        if self._paragraph is None:
            return None
        planned = self._pieces(self._paragraphs[self._paragraph :])
        if all(self._ready(audio_id) for audio_id, _ in planned):
            return 0.0
        speed = self._speed
        if speed is None:
            return None
        busy = 0.0
        if self._synthesizing is not None:
            elapsed = self._clock() - self._synthesizing_since
            busy = max(0.0, speed.synthesis_time(self._synthesizing_length) - elapsed)
        pieces = []
        coming = {self._synthesizing}  # a piece repeated later is ready with its first occurrence
        for audio_id, piece in planned:
            ready = self._ready(audio_id)
            pieces.append(
                PlannedPiece(
                    # Pieces from an earlier start are estimated, not read from disk under the lock.
                    duration=self._durations.get(audio_id, speed.duration(len(piece))),
                    ready=ready,
                    synthesis_left=0.0 if ready or audio_id in coming else speed.synthesis_time(len(piece)),
                )
            )
            coming.add(audio_id)
        return start_delay(pieces, busy)

    def _pieces(self, paragraphs: list[Paragraph]) -> list[tuple[str, str]]:
        """The pieces of these Paragraphs in play order: their audio ids and prepared text."""
        return [
            (audio_id, piece)
            for paragraph in paragraphs
            for audio_id, piece in zip(self._audio_ids(paragraph), paragraph.pieces, strict=True)
        ]

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
        """From the playback position to the end of the Text first, then the Paragraphs before it."""
        if not self._play_pressed:
            return None
        start = self._paragraph or 0
        for audio_id, piece in self._pieces(self._paragraphs[start:] + self._paragraphs[:start]):
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
                started = self._synthesizing_since = self._clock()
                self._synthesizing_length = len(text)
            result: Audio | str  # the audio, or why there is none
            try:
                if not self._registry.available(voice):
                    raise RuntimeError(f"{voice.label}: голос недоступен")
                result = self._registry.provider(voice).synthesize(text, voice.id, SPEED)
            except Exception as error:
                result = str(error)
            finished = self._clock()
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
                else:
                    self._speed = measured(self._speed, len(text), result.duration, finished - started)
                    self._durations[audio_id] = result.duration
                    if save_error is None:
                        self._saved_pieces.add(audio_id)
                    else:
                        self._audio[audio_id] = result  # it still plays until the program is closed
                        self._library_error = save_error
                self._start_when_safe()
                speed = self._speed
            if isinstance(result, Audio) and speed is not None:
                self._speeds.save(self._computer, speed)


def _title(content: str) -> str:
    words = content.split()
    if len(words) <= _TITLE_WORDS:
        return " ".join(words)
    return " ".join(words[:_TITLE_WORDS]).rstrip(",;:—–-") + "…"
