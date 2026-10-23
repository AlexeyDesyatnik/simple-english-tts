import io
import time
import wave

import pytest

from ozvuchka.core import Core
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeClock, FakeVoiceProvider


@pytest.fixture
def make_core(tmp_path):
    cores = []

    def make(provider):
        core = Core(VoiceRegistry([provider]), "fake:alice", clock=FakeClock(), data_dir=tmp_path / "data")
        cores.append(core)
        return core

    yield make
    for core in cores:
        core.close()


def wait_for(core, condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = core.snapshot()
        if condition(snapshot):
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"condition not reached; last snapshot: {core.snapshot()}")


def phrase_status(status):
    return lambda s: s["phrase"] is not None and s["phrase"]["status"] == status


def test_a_spoken_phrase_becomes_playable_audio_in_the_default_voice(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)

    core.speak("Hello, class.")

    snapshot = wait_for(core, phrase_status("ready"))
    assert snapshot["phrase"]["text"] == "Hello, class."
    assert provider.requests == [("Hello, class.", "alice", 1.0)]
    audio = core.audio(snapshot["phrase"]["audio"])
    with wave.open(io.BytesIO(audio.data)) as w:
        assert w.getnframes() / w.getframerate() == pytest.approx(1.3)


def test_a_phrase_has_no_audio_while_it_is_being_synthesized(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)

    core.speak("Hello.")

    snapshot = core.snapshot()
    assert snapshot["phrase"]["status"] == "synthesizing"
    assert snapshot["phrase"]["audio"] is None
    provider.finish_next()
    wait_for(core, phrase_status("ready"))


def test_a_new_phrase_replaces_the_one_still_being_synthesized(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.speak("First.")
    core.speak("Second one.")

    provider.finish_next()
    provider.finish_next()

    snapshot = wait_for(core, phrase_status("ready"))
    assert snapshot["phrase"]["text"] == "Second one."
    assert core.audio(snapshot["phrase"]["audio"]).duration == pytest.approx(1.1)


def test_a_phrase_fails_visibly_when_the_voice_provider_is_unavailable(make_core):
    core = make_core(FakeVoiceProvider(available=False))

    core.speak("Hello.")

    snapshot = wait_for(core, phrase_status("failed"))
    assert snapshot["phrase"]["audio"] is None
    assert snapshot["voices"][0]["available"] is False


def test_an_empty_phrase_is_rejected(make_core):
    core = make_core(FakeVoiceProvider())

    with pytest.raises(ValueError):
        core.speak("   ")

    assert core.snapshot()["phrase"] is None
