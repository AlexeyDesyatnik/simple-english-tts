"""Smoke-test the exact Windows zip or Linux tar.gz release artifact.

Unpack into a path with spaces and Cyrillic, start the actual launcher without opening a window, get the page,
synthesize "Hello." with real Kokoro and export MP3. Check second launch, heartbeat shutdown, data-only writes
and both early application-import and interpreter-initialization diagnostics.
Usage: python smoke_test.py <release zip or linux-x86_64 tar.gz>
"""

import io
import json
import os
import signal
import socket
import subprocess
import sys
import tarfile
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
    archive_path = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="Озвучка smoke ", ignore_cleanup_errors=True) as tmp:
        if archive_path.name.endswith(".zip"):
            assert sys.platform == "win32", "the Windows zip must be smoke-tested on Windows"
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp)
        elif archive_path.name.endswith("-linux-x86_64.tar.gz"):
            assert sys.platform == "linux", "the Linux archive must be smoke-tested on Linux"
            with tarfile.open(archive_path, "r:gz") as archive:
                launcher = archive.getmember(f"{APP}/{APP}.sh")
                assert launcher.mode & 0o111, "the Linux launcher is not executable in the tar"
                archive.extractall(tmp, filter="data")
        else:
            raise ValueError(f"Unknown release artifact: {archive_path.name}")
        folder = Path(tmp) / APP
        shipped = _files(folder)
        assert not any(p.parts[0] == "data" for p in shipped), "the archive has user data"
        assert Path("licenses", "NOTICE.txt") in shipped, "the archive has no licenses"
        if sys.platform == "linux":
            assert os.access(folder / f"{APP}.sh", os.X_OK), "the unpacked Linux launcher is not executable"

        log = folder / "data" / "ozvuchka.log"
        try:
            _run(folder, shipped, log)
            _check_early_failure(folder)
            _check_interpreter_failure(folder)
        except BaseException:
            print(f"--- {log}:", log.read_text(encoding="utf-8") if log.exists() else "(none)", sep="\n", flush=True)
            raise
    return 0


def _launcher(folder: Path) -> Path:
    return folder / f"{APP}.{'sh' if sys.platform == 'linux' else 'exe'}"


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
    if sys.platform == "win32":
        (config,) = (folder / "runtime").glob("python*._pth")
        saved = config.read_bytes()
        try:
            config.write_text("missing-standard-library\n", encoding="ascii")
            diagnostic = _failed_start(folder)
            assert "Fatal Python error" in diagnostic, diagnostic
            assert "encodings" in diagnostic, diagnostic
        finally:
            config.write_bytes(saved)
    else:
        encodings = folder / "runtime" / "lib" / "python3.12" / "encodings"
        saved = encodings.with_name("encodings.smoke-saved")
        encodings.rename(saved)
        try:
            diagnostic = _failed_start(folder)
            assert "Fatal Python error" in diagnostic, diagnostic
            assert "encodings" in diagnostic, diagnostic
        finally:
            saved.rename(encodings)
    print("OK: failure before Python logging preserves interpreter output and its exit code", flush=True)


def _failed_start(folder: Path) -> str:
    before = set((folder / "data").glob("startup-*.log"))
    result = subprocess.run(
        [str(_launcher(folder)), "--no-window", "--port", str(_free_port())],
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
    launcher = subprocess.Popen(
        [str(_launcher(folder)), "--no-window", "--port", str(port)],
        start_new_session=sys.platform == "linux",
    )
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
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
            else:
                os.killpg(launcher.pid, signal.SIGKILL)
    assert code == 0, f"the release launcher exited with code {code}"
    print("the program ended by itself after the page closed", flush=True)

    assert "Voice provider kokoro loaded" in log.read_text(encoding="utf-8"), "no log in the data folder"
    written = sorted(str(p) for p in _files(folder) - shipped if p.parts[0] != "data")
    assert not written, f"written outside data: {written}"
    print("OK: the log is in data/, nothing else was written into the program folder", flush=True)


def _start_again(folder: Path, port: int, log: Path) -> None:
    start = [str(_launcher(folder)), "--no-window", "--port", str(port)]
    second = subprocess.run(start, timeout=SECOND_START_TIMEOUT)
    assert second.returncode == 0, f"the second launch exited with code {second.returncode}"
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
        assert launcher.poll() is None, f"the release launcher exited with code {launcher.returncode}"
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
