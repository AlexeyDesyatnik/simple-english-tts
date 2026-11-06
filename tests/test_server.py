"""HTTP adapter tests: commands, snapshots, Voice samples and audio, save results, and request-header protection."""

import http.client
import json
import threading
import time
import urllib.request
from contextlib import closing
from urllib.parse import urlsplit

import pytest

from ozvuchka.core import Core
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeClock, FakeVoiceProvider


@pytest.fixture
def base_url(tmp_path):
    core = Core(
        VoiceRegistry([FakeVoiceProvider()]),
        "fake:alice",
        clock=FakeClock(),
        data_dir=tmp_path / "data",
        computer="classroom-pc",
    )
    server = make_server(core, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    core.close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.headers.get_content_type(), response.read()


def command(base_url, **body):
    request = urllib.request.Request(
        base_url + "/api/command", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())["result"]


def test_commands_events_snapshot_and_audio_pass_through(base_url):
    content_type, page = get(base_url + "/")
    assert content_type == "text/html"
    assert "Воспроизвести".encode() in page

    content_type, sample = get(base_url + "/api/sample/fake%3Ageorge")
    assert content_type == "audio/wav"
    assert sample.startswith(b"RIFF")

    assert command(base_url, command="page_alive") is None
    command(base_url, command="set_voice", voice="fake:george")
    command(base_url, command="set_speed", speed=0.9)
    command(base_url, command="set_text", text="Good morning.\nSit down, please.")
    command(base_url, command="play")

    deadline = time.monotonic() + 5
    while True:
        snapshot = json.loads(get(base_url + "/api/state")[1])
        if all(p["status"] == "ready" for p in snapshot["text"]["paragraphs"]):
            break
        assert time.monotonic() < deadline, snapshot
        time.sleep(0.01)
    command(base_url, command="paragraph_finished", paragraph=0)

    snapshot = json.loads(get(base_url + "/api/state")[1])
    assert snapshot["playback"]["paragraph"] == 1
    assert command(base_url, command="next_paragraph") is False  # the page keeps the Paragraph playing
    assert (snapshot["voice"], snapshot["speed"]) == ("fake:george", 0.9)
    content_type, audio = get(base_url + f"/api/audio/{snapshot['text']['paragraphs'][1]['audio'][0]}")
    assert content_type == "audio/wav"
    assert audio.startswith(b"RIFF")


def test_save_result_distinguishes_disk_confirmation_failure_and_stale_requests(base_url, tmp_path):
    state = json.loads(get(base_url + "/api/state")[1])
    context = state["save"]["context"]
    obstruction = tmp_path / "data" / "library.json.tmp"
    obstruction.mkdir()
    failed = command(base_url, command="save_text", text="HTTP edit.", context=context, sequence=2)
    assert failed["status"] == "failed"
    assert failed["error"].startswith("Не удалось сохранить Библиотеку")
    assert json.loads(get(base_url + "/api/state")[1])["save"] == failed
    obstruction.rmdir()
    saved = command(base_url, command="save_text", text="HTTP edit.", context=context, sequence=2)
    assert saved["status"] == "saved"
    assert saved["sequence"] == 2
    assert saved["text_id"] == failed["text_id"]
    stale = command(base_url, command="save_text", text="Old edit.", context=context, sequence=1)
    assert stale["status"] == "stale"
    command(base_url, command="new_text")
    assert command(base_url, command="save_text", text="Late edit.", context=context, sequence=3)["status"] == "stale"
    assert json.loads(get(base_url + "/api/state")[1])["text"] is None


@pytest.mark.parametrize(("host", "origin", "content_type", "status"), [
    ("127.0.0.1:{port}", None, "application/json", 200),
    ("localhost:{port}", "http://localhost:{port}", "application/json; charset=utf-8", 200),
    ("127.0.0.1:{port}", "http://127.0.0.1:{port}", "Application/JSON; charset=UTF-8", 200),
    ("localhost:{port}", "http://127.0.0.1:{port}", "application/json", 200),
    ("foreign.example:{port}", None, "application/json", 403),
    ("127.0.0.1:1", None, "application/json", 403),
    ("localhost", None, "application/json", 403),
    ("127.0.0.1:{port}.foreign.example", None, "application/json", 403),
    ("127.0.0.1:{port}@foreign.example", None, "application/json", 403),
    ("[::1]:{port}", None, "application/json", 403),
    (None, None, "application/json", 403),
    ("127.0.0.1:{port}", "https://foreign.example", "application/json", 403),
    ("127.0.0.1:{port}", "http://127.0.0.1:1", "application/json", 403),
    ("127.0.0.1:{port}", "https://127.0.0.1:{port}", "application/json", 403),
    ("127.0.0.1:{port}", "null", "application/json", 403),
    ("127.0.0.1:{port}", "", "application/json", 403),
    ("127.0.0.1:{port}", "http://127.0.0.1:{port}/", "application/json", 403),
    ("127.0.0.1:{port}", "http://127.0.0.1:{port}.foreign.example", "application/json", 403),
    ("127.0.0.1:{port}", None, "text/plain", 415),
    ("127.0.0.1:{port}", None, "application/x-www-form-urlencoded", 415),
    ("127.0.0.1:{port}", None, None, 415),
    ("127.0.0.1:{port}", "https://foreign.example", "text/plain;charset=UTF-8", 403),
])
def test_command_headers_allow_only_local_json_requests_without_rejected_side_effects(
    base_url, host, origin, content_type, status
):
    port = urlsplit(base_url).port
    body = b'{"command":"set_text","text":"Header marker."}'
    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.putrequest("POST", "/api/command", skip_host=True)
        for name, value in (("Host", host), ("Origin", origin), ("Content-Type", content_type)):
            if value is not None:
                connection.putheader(name, value.format(port=port))
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        assert response.status == status
        assert response.getheader("Access-Control-Allow-Origin") is None
        response.read()
    snapshot = json.loads(get(base_url + "/api/state")[1])
    if status == 200:
        assert snapshot["text"]["content"] == "Header marker."
    else:
        assert snapshot["text"] is None
        assert snapshot["library"] == []


@pytest.mark.parametrize("header", ["Host", "Origin", "Content-Type"])
def test_duplicate_security_headers_are_rejected_without_running_the_command(base_url, header):
    port = urlsplit(base_url).port
    headers = {"Host": f"127.0.0.1:{port}", "Origin": base_url, "Content-Type": "application/json"}
    body = b'{"command":"set_text","text":"Duplicate marker."}'
    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.putrequest("POST", "/api/command", skip_host=True)
        for name, value in headers.items():
            connection.putheader(name, value)
            if name == header:
                connection.putheader(name, value)
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        assert response.status == (415 if header == "Content-Type" else 403)
        response.read()
    assert json.loads(get(base_url + "/api/state")[1])["text"] is None


def test_foreign_host_cannot_read_the_application_and_preflight_does_not_allow_cors(base_url):
    port = urlsplit(base_url).port
    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.request("GET", "/api/state", headers={"Host": f"foreign.example:{port}"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
    request = urllib.request.Request(base_url + "/api/command", method="OPTIONS", headers={
        "Origin": "https://foreign.example", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    with pytest.raises(urllib.error.HTTPError) as rejected:
        urllib.request.urlopen(request, timeout=5)
    assert rejected.value.code >= 400
    assert rejected.value.headers.get("Access-Control-Allow-Origin") is None
    assert json.loads(get(base_url + "/api/state")[1])["library"] == []
