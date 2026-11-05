"""Isolate the real cancellation scenario so a stuck native thread cannot hang pytest."""

import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


def run_child(
    directory: Path, *, blocked: bool = False, load_timeout: float = 120, scenario_timeout: float = 30,
) -> str:
    ready = directory / "model-ready"
    ready.unlink(missing_ok=True)
    output = directory / "cancellation-child.log"
    command = [sys.executable, "-X", "utf8", "-u", "-m", "tests.kokoro_cancellation", str(ready)]
    if blocked:
        command.append("--blocked")
    failure = ""
    with output.open("wb") as log:
        child = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + load_timeout
            while not ready.exists():
                if child.poll() is not None:
                    failure = "exited before model readiness"
                    break
                if time.monotonic() >= deadline:
                    failure = f"model-loading deadline ({load_timeout} s)"
                    break
                time.sleep(0.05)
            if not failure:
                try:
                    child.wait(timeout=scenario_timeout)
                except subprocess.TimeoutExpired:
                    failure = f"scenario deadline ({scenario_timeout} s)"
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
    diagnostic = output.read_text(encoding="utf-8", errors="replace")
    assert not failure and child.returncode == 0, (
        f"Cancellation child PID {child.pid}: {failure or 'scenario failed'}; "
        f"exit code {child.returncode}\n{diagnostic}"
    )
    return diagnostic


def _blocked(ready: Path) -> None:
    ready.touch()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(threading.Event().wait)
        try:
            future.result(timeout=0.1)
        except TimeoutError:
            print("Blocked inference is still running", flush=True)
            traceback.print_exc()
        # Reproduce the original failure: executor exit waits for its stuck thread.


def _real(ready: Path) -> None:
    import onnxruntime

    from ozvuchka.kokoro import KokoroProvider
    from ozvuchka.voices import SynthesisCancelled

    provider = KokoroProvider(Path(__file__).resolve().parents[1] / "models" / "kokoro")
    provider.load()
    print("Model loaded", flush=True)
    ready.touch()
    cancel = threading.Event()
    started = threading.Event()
    run = onnxruntime.InferenceSession.run

    def inference(session, output_names, inputs, run_options=None):
        # Synchronize at the native boundary, after phonemization.
        started.set()
        return run(session, output_names, inputs, run_options)

    def synthesize():
        return provider.synthesize(
            "The children walked through the village and talked about the books they had read. " * 20,
            "bf_alice", 1.0, cancel,
        )

    with patch.object(onnxruntime.InferenceSession, "run", inference), ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(synthesize)
        try:
            assert started.wait(timeout=10), "Native inference did not start"
            print("Native inference started", flush=True)
            time.sleep(0.1)
            assert not future.done(), "The long synthesis must still be running when it is cancelled"
        finally:
            before = time.monotonic()
            cancel.set()
            print("Cancellation signalled", flush=True)
        try:
            future.result(timeout=5)
        except SynthesisCancelled:
            print(f"Real Kokoro cancellation returned after {time.monotonic() - before:.3f} s", flush=True)
        except TimeoutError:
            # Executor exit may block; preserve the original timeout before the parent kills us.
            traceback.print_exc()
            raise
        else:
            raise AssertionError("Cancelled synthesis returned audio")
    assert provider.synthesize("Good morning.", "bm_george", 1.0, threading.Event()).duration > 0
    print("Subsequent synthesis on the same loaded provider passed", flush=True)


if __name__ == "__main__":
    if "--blocked" in sys.argv:
        _blocked(Path(sys.argv[1]))
    else:
        _real(Path(sys.argv[1]))
