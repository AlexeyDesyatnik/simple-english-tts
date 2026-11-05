"""WAV audio returned by Voice providers and kept in the Library or played as a Voice sample."""

import io
import wave
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class Audio:
    """WAV bytes and their duration; other source formats must be converted by the provider."""

    data: bytes
    format: Literal["wav"]
    duration: float  # seconds

    @property
    def mime_type(self) -> str:
        return {"wav": "audio/wav"}[self.format]


def wav_from_samples(samples: ArrayLike, sample_rate: int) -> Audio:
    """Encodes float samples in [-1, 1] as 16-bit mono WAV."""
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767).round().astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return Audio(buffer.getvalue(), "wav", len(pcm) / sample_rate)


def audio_from_wav(data: bytes) -> Audio:
    with wave.open(io.BytesIO(data), "rb") as w:
        return Audio(data, "wav", w.getnframes() / w.getframerate())
