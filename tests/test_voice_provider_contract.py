"""One contract for every Voice provider: the fake one and the real Kokoro (slow)."""

import io
import threading
import time
import wave
from pathlib import Path

import pytest

from ozvuchka.voices import SynthesisCancelled
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


def test_every_voice_has_a_voice_sample_of_5_to_7_seconds(provider):
    for voice in provider.voices():
        sample = provider.sample(voice.id)
        assert sample is not None, voice.id
        assert 5.0 <= sample.duration <= 7.0, voice.id


def test_a_voice_it_does_not_have_has_no_sample(provider):
    assert provider.sample("nobody") is None


def test_a_cancelled_call_produces_no_audio_and_does_not_cancel_the_next_call(provider):
    cancel = threading.Event()
    cancel.set()
    voice = provider.voices()[0].id
    with pytest.raises(SynthesisCancelled):
        provider.synthesize("Hello, class.", voice, 1.0, cancel)
    assert provider.synthesize("Hello, class.", voice, 1.0, threading.Event()).duration > 0


def test_a_blocked_cancellation_child_is_killed_and_reaped_with_diagnostics(tmp_path, monkeypatch):
    import subprocess

    from tests import kokoro_cancellation

    children = []
    popen = subprocess.Popen

    def start(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", start)
    before = time.monotonic()
    with pytest.raises(AssertionError, match="scenario deadline") as failure:
        kokoro_cancellation.run_child(tmp_path, blocked=True, load_timeout=10, scenario_timeout=0.5)
    assert time.monotonic() - before < 15
    assert len(children) == 1
    assert children[0].poll() is not None
    assert "Blocked inference is still running" in str(failure.value)
    assert "TimeoutError" in str(failure.value)
    assert str(children[0].pid) in str(failure.value)


@pytest.mark.slow
def test_real_kokoro_interrupts_an_active_synthesis_and_can_synthesize_again(tmp_path):
    from tests.kokoro_cancellation import run_child

    print(run_child(tmp_path))
