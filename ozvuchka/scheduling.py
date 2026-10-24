"""Scheduling: how fast this computer synthesizes, and how long a Narration must wait before it can play
through without stopping."""

import contextlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ozvuchka.library import write_atomically

_FORMAT_VERSION = 1

_SAFETY = 1.15  # synthesis is counted 15% slower than measured, so a slower moment does not stop playback
_WEIGHT = 0.5  # how much the latest piece counts against everything measured before it
_SHORTEST = 0.001  # seconds; a short piece may finish within one tick of the clock


@dataclass(frozen=True)
class SynthesisSpeed:
    # Both count speech at Speed 1.0, so pieces read at different Speeds can be measured together.
    speed: float  # seconds of speech synthesized per second (0.44 on the Celeron, 1.85 on the i5)
    # Seconds of speech per character of prepared text, to estimate what is not synthesized yet. It belongs to
    # the Voice rather than the computer, but the Voices are close enough to share it.
    speech_per_character: float

    def synthesis_time(self, characters: int) -> float:
        """How long to allow for synthesizing this many characters."""
        return characters * self._cost * _SAFETY

    def duration(self, characters: int, voice_speed: float) -> float:
        """Seconds of speech in this many characters read at this Speed."""
        return characters * self.speech_per_character / voice_speed

    @property
    def _cost(self) -> float:
        return self.speech_per_character / self.speed


def measured(
    previous: SynthesisSpeed | None, characters: int, duration: float, seconds: float, voice_speed: float
) -> SynthesisSpeed:
    """The speed updated with one more piece of `duration` seconds of speech read at `voice_speed`, synthesized
    in `seconds`."""
    duration *= voice_speed  # as long as it would be at Speed 1.0
    latest = SynthesisSpeed(duration / max(seconds, _SHORTEST), duration / characters)
    if previous is None:
        return latest
    # Averaged as synthesis time per character, the quantity that adds up along a Narration.
    cost = _WEIGHT * latest._cost + (1 - _WEIGHT) * previous._cost
    spoken = _WEIGHT * latest.speech_per_character + (1 - _WEIGHT) * previous.speech_per_character
    return SynthesisSpeed(spoken / cost, spoken)


class SpeedRecords:
    """The Synthesis speed of every computer the program has run on, kept in the data folder by computer name,
    since the program folder moves between laptops on a flash drive (ADR-0001)."""

    def __init__(self, data_dir: Path):
        self._path = data_dir / "synthesis_speed.json"
        self._speeds: dict[str, SynthesisSpeed] = {}
        self._readable = True  # a damaged or newer file is left as it is
        try:
            if self._path.exists():
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(stored, dict) or stored.get("version") != _FORMAT_VERSION:
                    raise ValueError("damaged or newer")
                self._speeds = {
                    computer: SynthesisSpeed(float(s["speed"]), float(s["speech_per_character"]))
                    for computer, s in stored["computers"].items()
                }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self._readable = False  # it is measured again on the first piece

    def speed(self, computer: str) -> SynthesisSpeed | None:
        return self._speeds.get(computer)

    def save(self, computer: str, speed: SynthesisSpeed) -> None:
        self._speeds[computer] = speed
        if not self._readable:
            return
        stored = {
            "version": _FORMAT_VERSION,
            "computers": {
                c: {"speed": s.speed, "speech_per_character": s.speech_per_character} for c, s in self._speeds.items()
            },
        }
        with contextlib.suppress(OSError):  # only an estimate: without it the next start measures again
            write_atomically(self._path, json.dumps(stored, ensure_ascii=False, indent=1).encode())


@dataclass(frozen=True)
class PlannedPiece:
    duration: float  # seconds of speech, known or estimated
    ready: bool
    synthesis_left: float  # seconds of synthesis it still needs once its turn comes; 0 if ready


def start_delay(pieces: Iterable[PlannedPiece], busy: float) -> float:
    """How long to wait before playing these pieces in order, so that each is ready by the time it is reached.

    The pieces are synthesized in this order, one at a time, after `busy` seconds of synthesis already under way.
    """
    delay, synthesized, heard = 0.0, busy, 0.0
    for piece in pieces:
        if not piece.ready:
            synthesized += piece.synthesis_left
            delay = max(delay, synthesized - heard)
        heard += piece.duration
    return delay
