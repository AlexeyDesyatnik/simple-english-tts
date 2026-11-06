"""Smoke test of a release zip, as the teacher gets it.

Unpacks the zip, starts Озвучка.exe from the unpacked folder (without opening the window), gets the page,
synthesizes "Hello." with the real Kokoro and exports it as an MP3 response. A second start on the same port must end
by itself without starting another program. Then the page says it is closing, and the program must end by itself,
with its log in its data folder and nothing else written into the program folder.
Finally checks diagnostics for an early application import failure and a Python initialization failure.
Usage: python smoke_test.py <release zip>
"""

import io
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any

APP = "Озвучка"
START_TIMEOUT = 60.0  # seconds; the page is served while Kokoro loads in the background
SYNTHESIS_TIMEOUT = 420.0  # Kokoro loads first
SECOND_START_TIMEOUT = 60.0
EXIT_TIMEOUT = 60.0  # the program waits 10 s for a reload after the page closes


def main() -> int:
    zip_path = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="ozvuchka-smoke-", ignore_cleanup_errors=True) as tmp:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(tmp)
        folder = Path(tmp) / APP
        shipped = _files(folder)
        assert not any(p.parts[0] == "data" for p in shipped), "the zip has user data"
        assert Path("licenses", "NOTICE.txt") in shipped, "the zip has no licenses"

        log = folder / "data" / "ozvuchka.log"
        try:
            _run(folder, shipped, log)
            _check_early_failure(folder)
            _check_interpreter_failure(folder)
        except BaseException:
            print(f"--- {log}:", log.read_text(encoding="utf-8") if log.exists() else "(none)", sep="\n", flush=True)
            raise
    return 0


def _check_early_failure(folder: Path) -> None:
    """The actual release launcher must preserve a native-dependency import failure."""
    source = folder / "ozvuchka" / "core.py"
    saved = source.read_bytes()
    bytecode = {p: p.read_bytes() for p in source.parent.glob("__pycache__/core.*.pyc")}
    try:
        source.write_text("raise ImportError('release startup diagnostic check')\n", encoding="utf-8")
        for path in bytecode:
            path.unlink()
        assert "ImportError: release startup diagnostic check" in _failed_start(folder)
        assert "ImportError: release startup diagnostic check" in (folder / "data/ozvuchka.log").read_text(
            encoding="utf-8"
        )
        print("OK: an early import failure has its own diagnostic, identified by the release launcher", flush=True)
    finally:
        source.write_bytes(saved)
        for path, data in bytecode.items():
            path.write_bytes(data)


def _check_interpreter_failure(folder: Path) -> None:
    """Break Python's standard-library path so it fails before any application code runs."""
    (config,) = (folder / "runtime").glob("python*._pth")
    saved = config.read_bytes()
    try:
        config.write_text("missing-standard-library\n", encoding="ascii")
        diagnostic = _failed_start(folder)
        assert "Fatal Python error" in diagnostic, diagnostic
        assert "encodings" in diagnostic, diagnostic
        print("OK: failure before Python logging preserves interpreter output and its exit code", flush=True)
    finally:
        config.write_bytes(saved)


def _failed_start(folder: Path) -> str:
    before = set((folder / "data").glob("startup-*.log"))
    result = subprocess.run(
        [str(folder / f"{APP}.exe"), "--no-window", "--port", str(_free_port())],
        capture_output=True, text=True, encoding="utf-8", timeout=START_TIMEOUT,
    )
    assert result.returncode != 0, "the deliberately broken startup succeeded"
    (diagnostic,) = set((folder / "data").glob("startup-*.log")) - before
    assert diagnostic.name in result.stderr, result.stderr
    assert str(result.returncode) in result.stderr, result.stderr
    return diagnostic.read_text(encoding="utf-8")


def _run(folder: Path, shipped: set[Path], log: Path) -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    started = time.monotonic()
    launcher = subprocess.Popen([str(folder / f"{APP}.exe"), "--no-window", "--port", str(port)])
    try:
        _wait_for_page(url, launcher, log)
        print(f"page served after {time.monotonic() - started:.1f} s", flush=True)
        _command(url, "page_alive")
        _start_again(folder, port, log)
        _command(url, "set_text", text="Hello.")
        _command(url, "play")
        seconds = _wait_for_speech(url)
        print(f'"Hello." synthesized: {seconds:.2f} s of speech', flush=True)
        assert 0.3 < seconds < 3.0, seconds
        snapshot = json.loads(_get(url + "/api/state"))
        query = urllib.parse.urlencode({"voice": snapshot["voice"], "speed": snapshot["speed"]})
        request = f"{url}/api/export/{snapshot['text']['id']}?{query}"
        with urllib.request.urlopen(request, timeout=30) as response:
            mp3 = response.read()
            assert response.headers.get_content_type() == "audio/mpeg"
            assert response.headers["Cache-Control"] == "no-store"
            assert ".mp3" in response.headers["Content-Disposition"]
        assert len(mp3) > 1000 and mp3[0] == 0xFF and mp3[1] & 0xE0 == 0xE0
        assert all(p.suffix == ".wav" for p in (folder / "data" / "narrations").iterdir())
        print(f"OK: the offline release exported a {len(mp3)}-byte MPEG attachment", flush=True)

        _command(url, "page_closing")
        code = launcher.wait(timeout=EXIT_TIMEOUT)
    finally:
        if launcher.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
    assert code == 0, f"Озвучка.exe exited with code {code}"
    print("the program ended by itself after the page closed", flush=True)

    assert "Voice provider kokoro loaded" in log.read_text(encoding="utf-8"), "no log in the data folder"
    written = sorted(str(p) for p in _files(folder) - shipped if p.parts[0] != "data")
    assert not written, f"written outside data: {written}"
    print("OK: the log is in data\\, nothing else was written into the program folder", flush=True)


def _start_again(folder: Path, port: int, log: Path) -> None:
    start = [str(folder / f"{APP}.exe"), "--no-window", "--port", str(port)]
    second = subprocess.run(start, timeout=SECOND_START_TIMEOUT)
    assert second.returncode == 0, f"the second Озвучка.exe exited with code {second.returncode}"
    text = log.read_text(encoding="utf-8")
    assert "already running" in text, "the second start did not find the program running"
    assert text.count("Serving http") == 1, "the second start served the page too"
    print("a second start ended by itself, leaving the program running", flush=True)


def _files(folder: Path) -> set[Path]:
    return {p.relative_to(folder) for p in folder.rglob("*") if p.is_file()}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as response:
        data: bytes = response.read()
        return data


def _command(url: str, command: str, **body: Any) -> Any:
    request = urllib.request.Request(
        url + "/api/command",
        data=json.dumps({"command": command, **body}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())["result"]


def _wait_for_page(url: str, launcher: subprocess.Popen[bytes], log: Path) -> None:
    deadline = time.monotonic() + START_TIMEOUT
    while True:
        assert launcher.poll() is None, f"Озвучка.exe exited with code {launcher.returncode}"
        # after an error the launcher shows a message box and waits for it to be closed
        failed = log.exists() and " CRITICAL " in log.read_text(encoding="utf-8")
        assert not failed, "the program stopped with an error"
        try:
            assert b"<html" in _get(url + "/").lower()
            return
        except OSError:
            assert time.monotonic() < deadline, "the page was not served in time"
            time.sleep(1)


def _wait_for_speech(url: str) -> float:
    """Seconds of speech in the Text's audio, once it is synthesized."""
    deadline = time.monotonic() + SYNTHESIS_TIMEOUT
    while True:
        snapshot = json.loads(_get(url + "/api/state"))
        (paragraph,) = snapshot["text"]["paragraphs"]
        assert paragraph["status"] != "failed", paragraph
        if paragraph["status"] == "ready":
            break
        assert time.monotonic() < deadline, snapshot
        time.sleep(0.5)
    seconds = 0.0
    for audio_id in paragraph["audio"]:
        with wave.open(io.BytesIO(_get(f"{url}/api/audio/{audio_id}"))) as wav:
            seconds += wav.getnframes() / wav.getframerate()
    return seconds


if __name__ == "__main__":
    sys.exit(main())
