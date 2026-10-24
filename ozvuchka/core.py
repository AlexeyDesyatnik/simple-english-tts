"""The application core: all program state, driven by commands and read as a snapshot.

The core knows nothing about HTTP or the page. Synthesis runs on one background thread,
one piece at a time, so commands return at once and the page sees progress through the snapshot.
"""

import hashlib
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ozvuchka.audio import Audio
from ozvuchka.library import LibraryFiles, SavedText
from ozvuchka.scheduling import PlannedPiece, SpeedRecords, SynthesisSpeed, measured, start_delay
from ozvuchka.settings import Settings, SettingsFile
from ozvuchka.text import Paragraph, paragraphs
from ozvuchka.voices import Voice, VoiceRegistry

_SPEEDS = (0.8, 0.9, 1.0, 1.1)  # the Speeds the teacher chooses from
_DEFAULT_SPEED = 1.0
_TEXT_SIZES = (18, 22, 28, 36, 48, 64, 80)  # pixels; the large ones are for a projector
_DEFAULT_TEXT_SIZE = 22
_TITLE_WORDS = 5  # a Text's title in the Library is its first words


@dataclass(frozen=True)
class _Queued:
    """A Narration in the Narration queue: its pieces are synthesized from Paragraph `start` to the end, then the
    Paragraphs before it."""

    text_id: str
    voice: Voice
    speed: float
    start: int = 0

    @property
    def id(self) -> str:
        return f"{self.text_id}|{self.voice.key}|{self.speed}"


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
        self._clock = clock
        self._files = LibraryFiles(data_dir)
        self._settings = SettingsFile(data_dir)
        saved = self._settings.read()
        self._voice = (saved.voice and registry.voice(saved.voice)) or self._known_voice(default_voice)
        self._speed = saved.speed if saved.speed in _SPEEDS else _DEFAULT_SPEED
        self._text_size = saved.text_size if saved.text_size in _TEXT_SIZES else _DEFAULT_TEXT_SIZE

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
        self._queue: list[_Queued] = []  # the Narration queue; the first one is being synthesized
        # A piece's audio is saved in the Library; only one that could not be saved is kept in memory.
        self._saved_pieces = self._files.pieces()
        self._audio: dict[str, Audio] = {}
        self._failed: dict[str, str] = {}  # audio id -> why its piece could not be synthesized
        self._durations: dict[str, float] = {}  # audio id -> seconds, for the pieces synthesized since the start
        self._computer = computer
        self._speeds = SpeedRecords(data_dir)
        self._synthesis_speed = self._speeds.speed(computer)
        self._synthesizing: str | None = None
        self._synthesizing_since = 0.0
        self._synthesizing_length = 0  # characters
        # The playback position: the page plays, but the core decides what (ADR-0003).
        # "waiting" is after Play, until the Narration can play through without stopping to wait.
        self._state = "stopped"  # "waiting" | "playing" | "paused" | "stopped"
        self._paragraph: int | None = None
        self._ended_at: int | None = None  # the last Paragraph heard, once playback has reached the end of the Text

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
                self._drop_finished()  # an edit may leave a queued Narration with nothing to synthesize

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

    def set_voice(self, voice_key: str) -> None:
        """Chooses the Voice of the current Text's Narration; a Narration playing in another one stops."""
        voice = self._known_voice(voice_key)
        with self._lock:
            if voice != self._voice:
                self._voice = voice
                self._switch_narration()

    def set_speed(self, speed: float) -> None:
        """Chooses the Speed of the current Text's Narration; a Narration playing at another one stops."""
        if speed not in _SPEEDS:
            raise ValueError(f"speed {speed} is not one of {_SPEEDS}")
        with self._lock:
            if speed != self._speed:
                self._speed = speed
                self._switch_narration()

    # A− and A+ step from the size the core has, not the one the page last saw, so quick clicks all count.

    def bigger_text(self) -> None:
        self._step_text_size(1)

    def smaller_text(self) -> None:
        self._step_text_size(-1)

    def _step_text_size(self, step: int) -> None:
        with self._lock:
            at = _TEXT_SIZES.index(self._text_size) + step
            if 0 <= at < len(_TEXT_SIZES):
                self._text_size = _TEXT_SIZES[at]
                self._save_settings()

    def _known_voice(self, voice_key: str) -> Voice:
        voice = self._registry.voice(voice_key)
        if voice is None:
            raise ValueError(f"no voice {voice_key}")
        return voice

    def _save_settings(self) -> None:
        self._settings.save(Settings(self._voice.key, self._speed, self._text_size))

    def _switch_narration(self) -> None:
        """Remembers the Voice and Speed for the next start; the Narration playing is another one now."""
        self._save_settings()
        self._stop_playback()

    def enqueue(self) -> None:
        """Puts the current Text's Narration at the back of the Narration queue, unless it is ready or queued."""
        with self._work:
            if self._text is None:
                raise ValueError("no text to queue")
            narration = self._current_narration()
            if narration is not None and all(q.id != narration.id for q in self._queue):
                self._queue.append(narration)
                self._failed.clear()  # queueing again tries again what could not be synthesized
                self._drop_finished()
                self._work.notify()

    def cancel(self, narration_id: str) -> None:
        """Takes a Narration out of the Narration queue; its pieces already synthesized are kept, and a piece under
        way is finished. Playback of a cancelled Narration stops."""
        with self._lock:
            self._queue = [q for q in self._queue if q.id != narration_id]
            current = self._current_narration()
            if current is not None and current.id == narration_id:
                self._stop_playback()

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

    # Next, previous and repeat return whether playback moves, so the page throws away what it has scheduled.

    def next_paragraph(self) -> bool:
        """Plays the next Paragraph; after Stop, the first one."""
        with self._work:
            if self._ended_at is not None:
                return False
            return self._play_paragraph(self._readable_after(-1 if self._paragraph is None else self._paragraph))

    def previous_paragraph(self) -> bool:
        with self._work:
            here = self._position_or_last_heard()
            return self._play_paragraph(None if here is None else self._readable_before(here))

    def repeat_paragraph(self) -> bool:
        """Plays the current Paragraph again from its beginning; after the end of the Text, the last one."""
        with self._work:
            return self._play_paragraph(self._position_or_last_heard())

    def _position_or_last_heard(self) -> int | None:
        """Where previous and repeat start from: the playback position, or after the end the last Paragraph heard."""
        return self._paragraph if self._paragraph is not None else self._ended_at

    def _play_paragraph(self, index: int | None) -> bool:
        if index is None:
            return False
        self._state, self._paragraph = "waiting", index
        self._press_play()
        return True

    def _press_play(self) -> None:
        """Moves the current Text's Narration to the front of the Narration queue, synthesizing from the playback
        position."""
        self._ended_at = None
        narration = self._current_narration(start=self._paragraph or 0)
        if narration is not None:
            self._queue = [narration] + [q for q in self._queue if q.id != narration.id]
            self._failed.clear()  # Play tries again what could not be synthesized
            self._drop_finished()
            self._work.notify()
        self._start_when_safe()

    def _current_narration(self, start: int = 0) -> _Queued | None:
        if self._text_id is None:
            return None
        return _Queued(self._text_id, self._voice, self._speed, start)

    def pause(self) -> None:
        with self._lock:
            if self._state in ("waiting", "playing"):
                self._state = "paused"

    def stop(self) -> None:
        with self._lock:
            self._stop_playback()

    def _stop_playback(self) -> None:
        """Stops at the start of the Text: Play starts from its first Paragraph."""
        self._state, self._paragraph, self._ended_at = "stopped", None, None

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
                    self._state, self._ended_at = "stopped", index  # the end of the Text

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
            queue = self._queue_state()
            library_error = self._library_error
            voice, speed, text_size = self._voice.key, self._speed, self._text_size
        return {
            "voices": [
                {"id": v.key, "label": v.label, "available": self._registry.available(v)}
                for v in self._registry.voices()
            ],
            "voice": voice,
            "speeds": list(_SPEEDS),
            "speed": speed,
            "text_sizes": list(_TEXT_SIZES),
            "text_size": text_size,
            "library": library,
            "library_error": library_error,
            "queue": queue,
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

    def voice_sample(self, voice_key: str) -> Audio | None:
        voice = self._registry.voice(voice_key)
        return None if voice is None else self._registry.provider(voice).sample(voice.id)

    def _show(self, text: str | None) -> None:
        self._text = text
        self._paragraphs = [] if text is None else paragraphs(text)
        self._stop_playback()
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

    def _readable_before(self, index: int) -> int | None:
        return next((i for i in range(index - 1, -1, -1) if self._readable(i)), None)

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
        synthesis = self._synthesis_speed
        if synthesis is None:
            return None
        busy = self._busy(synthesis)
        pieces = []
        coming = {self._synthesizing}  # a piece repeated later is ready with its first occurrence
        for audio_id, piece in planned:
            ready = self._ready(audio_id)
            pieces.append(
                PlannedPiece(
                    # Pieces from an earlier start are estimated, not read from disk under the lock.
                    duration=self._durations.get(audio_id, synthesis.duration(len(piece), self._speed)),
                    ready=ready,
                    synthesis_left=0.0 if ready or audio_id in coming else synthesis.synthesis_time(len(piece)),
                )
            )
            coming.add(audio_id)
        return start_delay(pieces, busy)

    def _busy(self, speed: SynthesisSpeed) -> float:
        """Seconds of synthesis left in the piece under way."""
        if self._synthesizing is None:
            return 0.0
        elapsed = self._clock() - self._synthesizing_since
        return max(0.0, speed.synthesis_time(self._synthesizing_length) - elapsed)

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
        return [_audio_id(self._voice, self._speed, piece) for piece in paragraph.pieces]

    def _content(self, text_id: str) -> str:
        return next((t.content for t in self._library if t.id == text_id), "")

    def _queued_pieces(self, narration: _Queued) -> list[tuple[str, str]]:
        """A queued Narration's pieces in the order they are synthesized: their audio ids and prepared text."""
        all_paragraphs = _parsed(self._content(narration.text_id))
        ordered = all_paragraphs[narration.start :] + all_paragraphs[: narration.start]
        return [
            (_audio_id(narration.voice, narration.speed, piece), piece)
            for paragraph in ordered
            for piece in paragraph.pieces
        ]

    def _to_synthesize(self, audio_id: str) -> bool:
        return not self._ready(audio_id) and audio_id not in self._failed

    def _drop_finished(self) -> None:
        """A Narration leaves the queue once nothing is left to synthesize in it."""
        self._queue = [q for q in self._queue if any(self._to_synthesize(i) for i, _ in self._queued_pieces(q))]

    def _next_piece(self) -> tuple[str, str, Voice, float] | None:
        for narration in self._queue:
            for audio_id, piece in self._queued_pieces(narration):
                if self._to_synthesize(audio_id):
                    return audio_id, piece, narration.voice, narration.speed
        return None

    def _queue_state(self) -> list[dict[str, Any]]:
        """The queued Narrations with the seconds until each is ready; None until the Synthesis speed is known."""
        speed = self._synthesis_speed
        synthesized = 0.0 if speed is None else self._busy(speed)
        coming = {self._synthesizing}  # a piece shared with a Narration ahead is ready with it
        state = []
        for narration in self._queue:
            pieces = self._queued_pieces(narration)
            for audio_id, piece in pieces:
                if speed is not None and self._to_synthesize(audio_id) and audio_id not in coming:
                    synthesized += speed.synthesis_time(len(piece))
                coming.add(audio_id)
            state.append(
                {
                    "id": narration.id,
                    "text_id": narration.text_id,
                    "title": _title(self._content(narration.text_id)),
                    "voice": narration.voice.key,
                    "speed": narration.speed,
                    "synthesizing": any(audio_id == self._synthesizing for audio_id, _ in pieces),
                    "ready_in": None if speed is None else synthesized,
                }
            )
        return state

    def _claim_next_piece(self) -> tuple[str, str, Voice, float] | None:
        """Counts the next piece as under way from now on, so the Start delay and the queue's times run down."""
        piece = self._next_piece()
        if piece is not None:
            self._synthesizing = piece[0]
            self._synthesizing_since = self._clock()
            self._synthesizing_length = len(piece[1])
        return piece

    def _synthesize_pieces(self) -> None:
        piece = None
        while True:
            with self._work:
                while not self._closed and piece is None:
                    piece = self._claim_next_piece()
                    if piece is None:
                        self._work.wait()
                if self._closed or piece is None:
                    return
                audio_id, text, voice, voice_speed = piece
                started = self._synthesizing_since
            result: Audio | str  # the audio, or why there is none
            try:
                if not self._registry.available(voice):
                    raise RuntimeError(f"{voice.label}: голос недоступен")
                result = self._registry.provider(voice).synthesize(text, voice.id, voice_speed)
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
                    self._synthesis_speed = measured(
                        self._synthesis_speed, len(text), result.duration, finished - started, voice_speed
                    )
                    self._durations[audio_id] = result.duration
                    if save_error is None:
                        self._saved_pieces.add(audio_id)
                    else:
                        self._audio[audio_id] = result  # it still plays until the program is closed
                        self._library_error = save_error
                self._drop_finished()
                # The next piece is under way at once: between two pieces nothing would count down.
                piece = self._claim_next_piece()
                self._start_when_safe()
                speed = self._synthesis_speed
            if isinstance(result, Audio) and speed is not None:
                self._speeds.save(self._computer, speed)


def _audio_id(voice: Voice, speed: float, piece: str) -> str:
    """A piece's audio is the same for the same prepared text, Voice and Speed."""
    return hashlib.sha1(f"{voice.key}|{speed}|{piece}".encode()).hexdigest()[:16]


@lru_cache(maxsize=64)
def _parsed(content: str) -> list[Paragraph]:
    # The queue is looked through on every snapshot, twice a second; callers only slice the list.
    return paragraphs(content)


def _title(content: str) -> str:
    words = content.split()
    if len(words) <= _TITLE_WORDS:
        return " ".join(words)
    return " ".join(words[:_TITLE_WORDS]).rstrip(",;:—–-") + "…"
