"""One contract for every Voice provider: the fake one and the real Kokoro (slow)."""

import io
import wave
from pathlib import Path

import pytest

from tests.fakes import FakeVoiceProvider

MODELS = Path(__file__).resolve().parent.parent / "models"


@pytest.fixture(scope="module")
def kokoro():
    from ozvuchka.kokoro import KokoroProvider

    provider = KokoroProvider(MODELS / "kokoro")
    provider.load()
    return provider


@pytest.fixture(params=["fake", pytest.param("kokoro", marks=pytest.mark.slow)])
def provider(request):
    if request.param == "fake":
        return FakeVoiceProvider()
    return request.getfixturevalue("kokoro")


def test_lists_voices_with_russian_labels(provider):
    voices = provider.voices()
    assert voices
    for voice in voices:
        assert voice.provider == provider.id
        assert voice.gender in ("female", "male")
        assert voice.accent in ("gb", "us")
        assert any("а" <= ch <= "я" for ch in voice.label)
    assert len({v.id for v in voices}) == len(voices)


def test_is_available(provider):
    assert provider.available()


def test_synthesizes_a_phrase_into_audio_of_plausible_duration(provider):
    voice = provider.voices()[0].id

    audio = provider.synthesize("Hello, my name is Alice.", voice, 1.0)

    assert 0.8 < audio.duration < 4.0
    assert audio.format == "wav"
    with wave.open(io.BytesIO(audio.data)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() / w.getframerate() == pytest.approx(audio.duration)


def test_slower_speed_gives_longer_audio(provider):
    voice = provider.voices()[0].id

    normal = provider.synthesize("We read a book every day.", voice, 1.0)
    slow = provider.synthesize("We read a book every day.", voice, 0.8)

    assert slow.duration > normal.duration * 1.1
