"""MP3 export behavior through the public Core and HTTP seams."""

import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from array import array
from contextlib import closing
from urllib.parse import urlsplit

import pytest

from ozvuchka.audio import wav_from_samples
from ozvuchka.core import Core
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry
from tests.fakes import SAMPLE_RATE, FakeClock, FakeVoiceProvider


@pytest.fixture
def make_core(tmp_path):
    cores = []

    def make(provider):
        core = Core(
            VoiceRegistry([provider]),
            "fake:alice",
            clock=FakeClock(),
            data_dir=tmp_path / "data",
            computer="classroom-pc",
        )
        cores.append((core, provider))
        return core

    yield make
    for core, provider in cores:
        provider.finish_all()
        core.close()


@pytest.fixture
def core_and_provider(make_core):
    provider = FakeVoiceProvider()
    return make_core(provider), provider


@pytest.fixture
def base_url(tmp_path):
    provider = FakeVoiceProvider()
    core = Core(
        VoiceRegistry([provider]),
        "fake:alice",
        clock=FakeClock(),
        data_dir=tmp_path / "data",
        computer="classroom-pc",
    )
    server = make_server(core, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", core, provider
    server.shutdown()
    server.server_close()
    core.close()


def wait_ready(core):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = core.snapshot()
        if all(p["status"] in ("ready", "skipped") for p in snapshot["text"]["paragraphs"]):
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"Narration did not become ready: {core.snapshot()}")


def prepare(core, text="Hello."):
    core.set_text(text)
    core.play()
    return wait_ready(core)


def command(base_url, **body):
    request = urllib.request.Request(
        base_url + "/api/command", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())["result"]


def export_url(base_url, text_id, voice="fake:alice", speed="1.0"):
    return f"{base_url}/api/export/{text_id}?voice={voice}&speed={speed}"


def test_snapshot_shares_the_existing_paragraph_pause_and_piece_fade(core_and_provider):
    core, _ = core_and_provider

    assert core.snapshot()["audio_timing"] == {"paragraph_pause": 0.7, "piece_fade": 0.005}


def test_incomplete_empty_unknown_and_disallowed_exports_do_nothing_or_call_a_provider(core_and_provider):
    core, provider = core_and_provider
    core.set_text("Hello.")
    text_id = core.snapshot()["text"]["id"]
    before = core.snapshot()

    with pytest.raises(RuntimeError, match="Сначала подготовьте озвучку целиком"):
        core.export_narration(text_id, "fake:alice", 1.0)
    for bad_text, voice, speed in [
        ("missing", "fake:alice", 1.0),
        (text_id, "fake:missing", 1.0),
        (text_id, "fake:alice", 0.7),
    ]:
        with pytest.raises(ValueError):
            core.export_narration(bad_text, voice, speed)

    core.set_text("Прочитайте текст.")
    empty_id = core.snapshot()["text"]["id"]
    with pytest.raises(RuntimeError, match="Нет английского текста для экспорта"):
        core.export_narration(empty_id, "fake:alice", 1.0)

    assert provider.requests == []
    assert core.snapshot()["queue"] == before["queue"] == []
    assert core.snapshot()["save"]["status"] == before["save"]["status"]


def test_ready_narration_exports_with_an_unavailable_provider_and_a_safe_windows_filename(core_and_provider):
    core, provider = core_and_provider
    snapshot = prepare(core)
    text_id = snapshot["text"]["id"]
    core.rename_text(text_id, "  Урок: 1?  ")
    provider.set_available(False)
    before = core.snapshot()

    result = core.export_narration(text_id, "fake:alice", 1.0)

    assert result.data.startswith(b"\xff")
    assert len(result.data) > 100
    assert result.filename == "Урок 1 — Alice — 1×.mp3"
    assert core.snapshot() == before
    assert provider.requests == [("Hello.", "alice", 1.0)]


def test_requested_voice_and_speed_select_their_own_complete_narration(core_and_provider):
    core, provider = core_and_provider
    text_id = prepare(core)["text"]["id"]
    core.set_voice("fake:george")
    core.set_speed(0.8)

    with pytest.raises(RuntimeError, match="Сначала подготовьте озвучку целиком"):
        core.export_narration(text_id, "fake:george", 0.8)
    assert provider.requests == [("Hello.", "alice", 1.0)]

    core.play()
    wait_ready(core)
    result = core.export_narration(text_id, "fake:george", 0.8)

    assert result.filename == "Hello — George — 0.8×.mp3"
    assert provider.requests == [("Hello.", "alice", 1.0), ("Hello.", "george", 0.8)]


def test_ready_pieces_kept_only_in_memory_after_a_write_failure_can_be_exported(core_and_provider, monkeypatch):
    core, _ = core_and_provider
    core.set_text("Hello.")
    monkeypatch.setattr("os.replace", lambda *_: (_ for _ in ()).throw(OSError("simulated write failure")))
    core.play()
    snapshot = wait_ready(core)
    assert snapshot["library_error"].startswith("Не удалось сохранить озвучку")

    result = core.export_narration(snapshot["text"]["id"], "fake:alice", 1.0)

    assert result.data.startswith(b"\xff")


def test_a_missing_piece_is_a_controlled_retryable_error(core_and_provider, tmp_path):
    core, _ = core_and_provider
    snapshot = prepare(core)
    audio_id = snapshot["text"]["paragraphs"][0]["audio"][0]
    (tmp_path / "data" / "narrations" / f"{audio_id}.wav").unlink()
    before = core.snapshot()

    with pytest.raises(RuntimeError, match="Не удалось прочитать озвучку. Попробуйте ещё раз."):
        core.export_narration(snapshot["text"]["id"], "fake:alice", 1.0)

    assert core.snapshot() == before


def test_export_joins_pieces_fades_edges_and_adds_only_one_pause_between_readable_paragraphs(
    make_core, monkeypatch
):
    class ConstantProvider(FakeVoiceProvider):
        def synthesize(self, text, voice, speed, cancel=None):
            self.requests.append((text, voice, speed))
            return wav_from_samples([0.25] * 2400, SAMPLE_RATE)

    class RecordingEncoder:
        def __init__(self):
            self.pcm = bytearray()
            encoders.append(self)

        def set_bit_rate(self, value):
            assert value == 128

        def set_in_sample_rate(self, value):
            assert value == 24000

        def set_channels(self, value):
            assert value == 1

        def set_quality(self, value):
            assert value == 2

        def silence(self):
            pass

        def encode(self, data):
            self.pcm.extend(data)
            return b""

        def flush(self):
            return b"MP3"

    encoders: list[RecordingEncoder] = []
    monkeypatch.setattr("lameenc.Encoder", RecordingEncoder)
    provider = ConstantProvider()
    core = make_core(provider)
    long_paragraph = "This is a sentence that is long enough to be split into pieces. " * 10
    core.set_text(f"{long_paragraph}\nПрочитайте текст.\nGoodbye.")
    core.play()
    snapshot = wait_ready(core)

    result = core.export_narration(snapshot["text"]["id"], "fake:alice", 1.0)

    assert len(snapshot["text"]["paragraphs"][0]["audio"]) == 2
    assert result.data == b"MP3"
    samples = array("h")
    samples.frombytes(bytes(encoders[0].pcm))
    assert len(samples) == 24000
    assert samples[0] == 0
    assert samples[1] == 68
    assert samples[119] == 8124
    assert samples[120] == 8192
    assert samples[2279] == 8192
    assert samples[2399] == 68
    assert samples[2400] == 0
    assert samples[2401] == 68
    assert samples[2519] == 8124
    assert samples[2520] == 8192
    assert samples[4800:21600] == array("h", [0]) * 16800
    assert samples[21600] == 0
    assert samples[21601] == 68
    assert samples[-1] == 68


def test_export_does_not_hold_the_core_lock_while_encoding(core_and_provider, monkeypatch):
    core, _ = core_and_provider
    text_id = prepare(core)["text"]["id"]
    entered = threading.Event()
    release = threading.Event()

    class BlockingEncoder:
        def __init__(self):
            pass

        def set_bit_rate(self, value):
            pass

        def set_in_sample_rate(self, value):
            pass

        def set_channels(self, value):
            pass

        def set_quality(self, value):
            pass

        def silence(self):
            pass

        def encode(self, data):
            entered.set()
            assert release.wait(timeout=5)
            return b""

        def flush(self):
            return b"MP3"

    monkeypatch.setattr("lameenc.Encoder", BlockingEncoder)
    exporting = threading.Thread(target=lambda: core.export_narration(text_id, "fake:alice", 1.0))
    exporting.start()
    assert entered.wait(timeout=5)
    snapshot_done = threading.Event()

    def read_snapshot():
        core.snapshot()
        snapshot_done.set()

    reading = threading.Thread(target=read_snapshot)
    reading.start()
    try:
        assert snapshot_done.wait(timeout=1), "Core snapshot waited for MP3 encoding"
    finally:
        release.set()
        exporting.join(timeout=5)
        reading.join(timeout=5)
    assert not exporting.is_alive()


def test_http_exports_mpeg_attachment_with_utf8_filename_and_no_store(base_url):
    url, core, _ = base_url
    text_id = prepare(core)["text"]["id"]
    core.rename_text(text_id, "Урок: 1?")

    with urllib.request.urlopen(export_url(url, text_id, "fake%3Aalice"), timeout=5) as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "audio/mpeg"
        assert response.headers["Cache-Control"] == "no-store"
        disposition = response.headers["Content-Disposition"]
        assert disposition.startswith('attachment; filename="narration.mp3"; filename*=UTF-8\'\'')
        assert "%D0%A3%D1%80%D0%BE%D0%BA%201%20%E2%80%94%20Alice%20%E2%80%94%201%C3%97.mp3" in disposition
        data = response.read()

    assert data.startswith(b"\xff")
    assert len(data) > 100


def test_http_rejects_malformed_unknown_and_incomplete_exports_with_json_errors(base_url):
    url, core, provider = base_url
    core.set_text("Hello.")
    text_id = core.snapshot()["text"]["id"]
    before = core.snapshot()
    cases = [
        (f"{url}/api/export/{text_id}", 400),
        (f"{url}/api/export/{text_id}?voice=fake%3Aalice", 400),
        (f"{url}/api/export/{text_id}?speed=1.0", 400),
        (export_url(url, text_id, speed="fast"), 400),
        (export_url(url, "missing"), 400),
        (export_url(url, text_id, "fake%3Amissing"), 400),
        (export_url(url, text_id, speed="0.7"), 400),
        (f"{url}/api/export/{text_id}?voice=fake%3Aalice&speed=1.0&extra=1", 400),
    ]

    for request_url, expected in cases:
        with pytest.raises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(request_url, timeout=5)
        assert rejected.value.code == expected
        assert rejected.value.headers.get_content_type() == "application/json"
        assert "error" in json.loads(rejected.value.read())

    with pytest.raises(urllib.error.HTTPError) as rejected:
        urllib.request.urlopen(export_url(url, text_id, speed="1.0"), timeout=5)
    assert rejected.value.code == 409
    assert json.loads(rejected.value.read())["error"] == "Сначала подготовьте озвучку целиком"
    assert core.snapshot() == before
    assert provider.requests == []


def test_http_foreign_host_cannot_export(base_url):
    url, core, _ = base_url
    text_id = prepare(core)["text"]["id"]
    before = core.snapshot()
    port = urlsplit(url).port

    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.request(
            "GET", f"/api/export/{text_id}?voice=fake%3Aalice&speed=1.0", headers={"Host": f"foreign.example:{port}"}
        )
        response = connection.getresponse()
        assert response.status == 403
        assert response.headers.get_content_type() == "application/json"
        response.read()

    assert core.snapshot() == before


def test_http_encoding_failure_is_a_readable_json_error_not_an_empty_download(base_url, monkeypatch):
    url, core, _ = base_url
    text_id = prepare(core)["text"]["id"]

    class BrokenEncoder:
        def __init__(self):
            raise RuntimeError("simulated encoder failure")

    monkeypatch.setattr("lameenc.Encoder", BrokenEncoder)
    with pytest.raises(urllib.error.HTTPError) as rejected:
        urllib.request.urlopen(export_url(url, text_id), timeout=5)

    assert rejected.value.code == 500
    assert rejected.value.headers.get_content_type() == "application/json"
    assert json.loads(rejected.value.read())["error"] == "Не удалось создать MP3. Попробуйте ещё раз."
