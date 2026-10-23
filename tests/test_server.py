"""Smoke test: a command, the snapshot and the audio pass through the HTTP layer."""

import json
import threading
import time
import urllib.request

import pytest

from ozvuchka.core import Core
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeClock, FakeVoiceProvider


@pytest.fixture
def base_url(tmp_path):
    core = Core(VoiceRegistry([FakeVoiceProvider()]), "fake:alice", clock=FakeClock(), data_dir=tmp_path / "data")
    server = make_server(core, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    core.close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.headers.get_content_type(), response.read()


def test_command_snapshot_and_audio_pass_through(base_url):
    content_type, page = get(base_url + "/")
    assert content_type == "text/html"
    assert b"Play" in page

    request = urllib.request.Request(
        base_url + "/api/command",
        data=json.dumps({"command": "speak", "text": "Good morning."}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request, timeout=5).close()

    deadline = time.monotonic() + 5
    while True:
        snapshot = json.loads(get(base_url + "/api/state")[1])
        if snapshot["phrase"] and snapshot["phrase"]["status"] == "ready":
            break
        assert time.monotonic() < deadline, snapshot
        time.sleep(0.01)

    content_type, audio = get(base_url + f"/api/audio/{snapshot['phrase']['audio']}")
    assert content_type == "audio/wav"
    assert audio.startswith(b"RIFF")
