"""The offline Voice provider: Kokoro-82M int8 fed with misaki phonemes (ADR-0002)."""

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from ozvuchka.audio import Audio, wav_from_samples
from ozvuchka.voices import Voice

if TYPE_CHECKING:  # imported for real in load(): it takes seconds
    from kokoro_onnx import Kokoro

SPACY_MODEL = "en_core_web_sm"
SAMPLE_RATE = 24000

# In the order the teacher sees them; Alice is the default Voice, George the default male one.
VOICES = [
    ("bf_alice", "Alice", "female"),
    ("bf_emma", "Emma", "female"),
    ("bf_isabella", "Isabella", "female"),
    ("bf_lily", "Lily", "female"),
    ("bm_george", "George", "male"),
    ("bm_fable", "Fable", "male"),
    ("bm_lewis", "Lewis", "male"),
    ("bm_daniel", "Daniel", "male"),
]
DEFAULT_VOICE = "kokoro:bf_alice"
GENDER_LABELS = {"female": "женский", "male": "мужской"}


class KokoroProvider:
    id = "kokoro"

    def __init__(self, model_dir: Path):
        self._model_dir = model_dir
        self._tts: Kokoro | None = None
        self._g2p: Any = None  # misaki.en.G2P; misaki has no type information
        self._lock = threading.Lock()  # the model and misaki are used by one synthesis at a time

    def voices(self) -> list[Voice]:
        return [
            Voice(self.id, voice, f"{name} — {GENDER_LABELS[gender]}, британский", gender, "gb")
            for voice, name, gender in VOICES
        ]

    def available(self) -> bool:
        return self._tts is not None

    def load(self) -> None:
        """Loads the model, spaCy and misaki; takes seconds, longer from a flash drive."""
        import spacy

        if not spacy.util.is_package(SPACY_MODEL):
            # otherwise misaki would try to download it from the internet
            raise RuntimeError(f"spaCy model {SPACY_MODEL} is not installed; run tools\\build.bat dev")
        from kokoro_onnx import Kokoro
        from misaki import en, espeak

        g2p = en.G2P(trf=False, british=True, fallback=espeak.EspeakFallback(british=True))
        tts = Kokoro(str(self._model_dir / "kokoro-int8.onnx"), str(self._model_dir / "voices.npz"))
        with self._lock:
            self._g2p, self._tts = g2p, tts

    def synthesize(self, text: str, voice: str, speed: float) -> Audio:
        if self._tts is None:
            raise RuntimeError("Kokoro is not loaded yet")
        with self._lock:
            phonemes, _ = self._g2p(text)
            phonemes = phonemes.replace("❓", "")
            if phonemes.strip():
                samples, _ = self._tts.create(phonemes, voice=voice, speed=speed, is_phonemes=True)
            else:
                samples = np.zeros(0, dtype=np.float32)
        return wav_from_samples(samples, SAMPLE_RATE)
