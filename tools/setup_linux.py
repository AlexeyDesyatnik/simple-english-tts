"""Build the isolated Linux development runtime from the shared pinned dependencies and assets."""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
CACHE = ROOT / ".cache"
RUNTIME = ROOT / "runtime-linux"
MODELS = ROOT / "models" / "kokoro"


def step(text: str) -> None:
    print(f"\n=== {text}", flush=True)


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_sha256: str) -> None:
    if destination.exists() and sha256(destination) == expected_sha256:
        print(f"  cached: {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(3):
        try:
            print(f"  downloading {url}", flush=True)
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
            actual = sha256(partial)
            if actual != expected_sha256:
                raise RuntimeError(f"Checksum mismatch for {destination.name}: got {actual}")
            partial.replace(destination)
            return
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(3)


def main() -> int:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("This setup supports Linux x86-64 only")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"Run with CPython 3.12, not {platform.python_version()}")

    assets = json.loads((TOOLS / "build-assets.json").read_text(encoding="utf-8"))
    spacy = assets["spacy_model"]
    kokoro = assets["kokoro"]

    step("Python 3.12 virtual environment")
    python = RUNTIME / "bin" / "python"
    if not python.exists():
        run(sys.executable, "-m", "venv", str(RUNTIME))
    print(f"  OK: {python}")

    step("Pinned packages from wheels")
    pip = [
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--only-binary=:all:",
    ]
    run(
        *pip,
        "-c",
        str(TOOLS / "constraints.txt"),
        "-r",
        str(TOOLS / "requirements.txt"),
        "-r",
        str(TOOLS / "requirements-dev.txt"),
    )
    run(*pip, "--no-deps", "-r", str(TOOLS / "requirements-nodeps.txt"))

    step(f"spaCy model ({spacy['name']} {spacy['version']})")
    installed = subprocess.run(
        [str(python), "-c", f"import importlib.metadata as m; print(m.version('{spacy['name']}'))"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    wheel_name = f"{spacy['name']}-{spacy['version']}-py3-none-any.whl"
    wheel = CACHE / wheel_name
    download(
        f"https://github.com/explosion/spacy-models/releases/download/{spacy['name']}-{spacy['version']}/{wheel_name}",
        wheel,
        spacy["sha256"],
    )
    if installed != spacy["version"]:
        run(*pip, "--no-deps", "--force-reinstall", str(wheel))
    else:
        print("  already installed")

    step("Kokoro model and British voices")
    MODELS.mkdir(parents=True, exist_ok=True)
    model = MODELS / "kokoro-int8.onnx"
    if not model.exists():
        model_download = CACHE / "kokoro-int8.onnx"
        download(
            f"{kokoro['repository']}/{kokoro['model']['path']}",
            model_download,
            kokoro["model"]["sha256"],
        )
        shutil.copyfile(model_download, model)
    else:
        print("  cached: kokoro-int8.onnx")
    voice_dir = CACHE / "kokoro-voices"
    for voice, voice_sha256 in kokoro["voices"].items():
        download(f"{kokoro['repository']}/voices/{voice}.bin", voice_dir / f"{voice}.bin", voice_sha256)
    run(str(python), str(TOOLS / "pack_kokoro_voices.py"), str(voice_dir), str(MODELS / "voices.npz"))

    step("Voice samples")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(ROOT))
    subprocess.run(
        [str(python), str(TOOLS / "make_voice_samples.py"), str(MODELS)],
        cwd=ROOT,
        env=env,
        check=True,
    )

    step("Native imports")
    run(
        str(python),
        "-c",
        "import kokoro_onnx, lameenc, misaki.en, onnxruntime, spacy, ozvuchka; "
        f"assert spacy.util.is_package('{spacy['name']}'); print('  imports OK')",
        cwd=ROOT,
    )
    print("\nDone. Run the real provider checks with: runtime-linux/bin/python -m pytest -m slow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
