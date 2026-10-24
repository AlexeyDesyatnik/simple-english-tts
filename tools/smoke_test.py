"""Smoke test of a release zip, as the teacher gets it.

Unpacks the zip, starts Озвучка.exe from the unpacked folder (without opening the window), gets the page and
synthesizes "Hello." with the real Kokoro. Then the page says it is closing, and the program must end by itself,
with its log in its data folder and nothing else written into the program folder.
Usage: python smoke_test.py <release zip>
"""

import io
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any

APP = "Озвучка"
START_TIMEOUT = 300.0  # seconds; Kokoro loads before the page is served
SYNTHESIS_TIMEOUT = 120.0
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
        except BaseException:
            print(f"--- {log}:", log.read_text(encoding="utf-8") if log.exists() else "(none)", sep="\n", flush=True)
            raise
    return 0


def _run(folder: Path, shipped: set[Path], log: Path) -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    started = time.monotonic()
    launcher = subprocess.Popen([str(folder / f"{APP}.exe"), "--no-window", "--port", str(port)])
    try:
        _wait_for_page(url, launcher, log)
        print(f"page served after {time.monotonic() - started:.1f} s", flush=True)
        _command(url, "page_alive")
        _command(url, "set_text", text="Hello.")
        _command(url, "play")
        seconds = _wait_for_speech(url)
        print(f'"Hello." synthesized: {seconds:.2f} s of speech', flush=True)
        assert 0.3 < seconds < 3.0, seconds

        _command(url, "page_closing")
        code = launcher.wait(timeout=EXIT_TIMEOUT)
    finally:
        if launcher.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
    assert code == 0, f"Озвучка.exe exited with code {code}"
    print("the program ended by itself after the page closed", flush=True)

    assert "Kokoro loaded" in log.read_text(encoding="utf-8"), "no log in the data folder"
    written = sorted(str(p) for p in _files(folder) - shipped if p.parts[0] != "data")
    assert not written, f"written outside data: {written}"
    print("OK: the log is in data\\, nothing else was written into the program folder", flush=True)


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
