"""Synthesized audio as the page receives it."""

import io
import wave
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Audio:
    data: bytes
    format: str  # "wav" (Kokoro); later "mp3" (Edge)
    duration: float  # seconds

    @property
    def mime_type(self) -> str:
        return {"wav": "audio/wav", "mp3": "audio/mpeg"}[self.format]


def wav_from_samples(samples, sample_rate: int) -> Audio:
    """Encodes float samples in [-1, 1] as 16-bit mono WAV."""
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767).round().astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return Audio(buffer.getvalue(), "wav", len(pcm) / sample_rate)
