"""In-memory MP3 export of ready Narration pieces, with the same joins and pauses as browser playback."""

import io
import re
import sys
import wave
from array import array
from collections.abc import Iterable
from dataclasses import dataclass

import lameenc

from ozvuchka.audio import PARAGRAPH_PAUSE, PIECE_FADE, Audio

_SAMPLE_RATE = 24000
_BIT_RATE = 128
_TITLE_LENGTH = 80
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class ExportResult:
    data: bytes
    filename: str


class ExportError(RuntimeError):
    """A Narration cannot be exported right now; the teacher can correct this or retry."""


def encode_mp3(
    paragraphs: Iterable[Iterable[Audio]], *, title: str, voice_label: str, speed: float
) -> ExportResult:
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(_BIT_RATE)
    encoder.set_in_sample_rate(_SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    encoder.silence()
    encoded = bytearray()
    for index, pieces in enumerate(paragraphs):
        if index:
            encoded.extend(encoder.encode(b"\0\0" * round(PARAGRAPH_PAUSE * _SAMPLE_RATE)))
        for audio in pieces:
            encoded.extend(encoder.encode(_faded_pcm(audio)))
    encoded.extend(encoder.flush())
    return ExportResult(bytes(encoded), _filename(title, voice_label, speed))


def _faded_pcm(audio: Audio) -> bytes:
    try:
        with wave.open(io.BytesIO(audio.data), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != _SAMPLE_RATE:
                raise ExportError("Не удалось прочитать озвучку. Попробуйте ещё раз.")
            data = wav.readframes(wav.getnframes())
    except (EOFError, wave.Error) as error:
        raise ExportError("Не удалось прочитать озвучку. Попробуйте ещё раз.") from error
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder != "little":
        samples.byteswap()
    fade = min(round(PIECE_FADE * _SAMPLE_RATE), len(samples) // 2)
    for index in range(fade):
        samples[index] = round(samples[index] * index / fade)
        samples[-index - 1] = round(samples[-index - 1] * (index + 1) / fade)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def _filename(title: str, voice_label: str, speed: float) -> str:
    safe_title = " ".join(_INVALID_FILENAME.sub(" ", title).split()).strip(" .")[:_TITLE_LENGTH].rstrip(" .")
    voice_name = " ".join(_INVALID_FILENAME.sub(" ", voice_label.partition(" — ")[0]).split()).strip(" .")
    return f"{safe_title or 'Озвучка'} — {voice_name or 'Голос'} — {speed:g}×.mp3"
