"""Test doubles for the application core's seam: a Voice provider and a clock."""

import threading

from ozvuchka.audio import Audio, wav_from_samples
from ozvuchka.voices import Voice

SAMPLE_RATE = 24000


class FakeVoiceProvider:
    """Speaks with two made-up Voices. Speech lasts 0.1 s per character at Speed 1.0.

    With manual=True each synthesis waits until the test calls finish_next(),
    so a test can look at the program while a piece is still being synthesized.
    """

    id = "fake"

    def __init__(self, manual: bool = False, available: bool = True):
        self.requests: list[tuple[str, str, float]] = []
        self._manual = manual
        self._available = available
        self._go = threading.Semaphore(0)

    def voices(self) -> list[Voice]:
        return [
            Voice(self.id, "alice", "Alice — женский, британский", "female", "gb"),
            Voice(self.id, "george", "George — мужской, британский", "male", "gb"),
        ]

    def available(self) -> bool:
        return self._available

    def synthesize(self, text: str, voice: str, speed: float) -> Audio:
        self.requests.append((text, voice, speed))
        if self._manual and not self._go.acquire(timeout=5):
            raise TimeoutError("the test never called finish_next()")
        seconds = 0.1 * len(text) / speed
        return wav_from_samples([0.0] * round(seconds * SAMPLE_RATE), SAMPLE_RATE)

    def finish_next(self) -> None:
        self._go.release()


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
