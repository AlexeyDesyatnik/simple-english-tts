"""Build the self-contained Linux x86-64 portable folder and tar.gz archive (ADR-0001)."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import download_linux_python
from setup_linux import CACHE, TOOLS, download

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PROGRAM = DIST / "Озвучка"
RUNTIME = PROGRAM / "runtime"
MODELS = PROGRAM / "models" / "kokoro"
APP_NAME = "Озвучка"

LAUNCHER = """#!/bin/sh
set -u
program_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
cd "$program_dir" || exit 1
data="$program_dir/data"
if ! mkdir -p "$data"; then
    printf 'Не удалось создать папку data для диагностики запуска.\n' >&2
    exit 1
fi
output="$data/startup-$$.log"
if ! : > "$output"; then
    printf 'Не удалось сохранить диагностику запуска в %s.\n' "$output" >&2
    exit 1
fi
OZVUCHKA_LAUNCHER=1
export OZVUCHKA_LAUNCHER
"$program_dir/runtime/bin/python3.12" -X utf8 -m ozvuchka --app "$@" > "$output" 2>&1
status=$?
if [ "$status" -eq 0 ]; then
    rm -f "$output"
    exit 0
fi
printf 'Озвучка завершилась с ошибкой (код %s).\n' "$status" >&2
printf 'Подробности — %s.\n' "$output" >&2
if [ -s "$output" ]; then
    cat "$output" >&2
else
    printf 'Python не вывел дополнительных сведений.\n' >&2
fi
exit "$status"
"""


def step(text: str) -> None:
    print(f"\n=== {text}", flush=True)


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def copy_licenses() -> None:
    step("Third-party licenses")
    target = PROGRAM / "licenses"
    target.mkdir(parents=True)
    for source in (TOOLS / "licenses").iterdir():
        if source.name != "NOTICE.txt":
            shutil.copyfile(source, target / source.name)
    shutil.copyfile(TOOLS / "licenses" / "NOTICE-linux.txt", target / "NOTICE.txt")

    python_target = target / "python"
    python_target.mkdir()
    shutil.copyfile(RUNTIME / "lib" / "python3.12" / "LICENSE.txt", python_target / "LICENSE.txt")
    libraries_target = python_target / "libraries"
    libraries_target.mkdir()
    python_assets = json.loads((TOOLS / "build-assets.json").read_text(encoding="utf-8"))["linux_python"]
    license_archive = CACHE / "python-build-standalone-licenses.tar.gz"
    download(python_assets["licenses_url"], license_archive, python_assets["licenses_sha256"])
    with tarfile.open(license_archive, "r:gz") as source_archive:
        for member in source_archive.getmembers():
            name = Path(member.name).name
            if member.isfile() and (name.startswith("LICENSE.") or name == "python-licenses.rst"):
                license_source = source_archive.extractfile(member)
                assert license_source is not None
                with license_source:
                    (libraries_target / name).write_bytes(license_source.read())

    site = RUNTIME / "lib" / "python3.12" / "site-packages"
    for info in site.glob("*.dist-info"):
        package = re.sub(r"-[^-]+\.dist-info$", "", info.name)
        for source in info.rglob("*"):
            if source.is_file() and re.match(r"^(LICEN[CS]E|COPYING|NOTICE)", source.name, re.IGNORECASE):
                destination = target / "packages" / package / source.relative_to(info)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
    onnx = target / "packages" / "onnxruntime"
    onnx.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(site / "onnxruntime" / "LICENSE", onnx / "LICENSE")
    shutil.copyfile(site / "onnxruntime" / "ThirdPartyNotices.txt", onnx / "ThirdPartyNotices.txt")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("The Linux release build supports Linux x86-64 only")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"Run the build with CPython 3.12, not {platform.python_version()}")

    version = args.version
    if not version:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        version = described.stdout.strip() if described.returncode == 0 else "dev"
    version = version.removeprefix("v")

    step(f"Release {version} into {PROGRAM}")
    shutil.rmtree(PROGRAM, ignore_errors=True)
    PROGRAM.mkdir(parents=True)
    shutil.copytree(
        ROOT / "ozvuchka",
        PROGRAM / "ozvuchka",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    step("Baseline standalone CPython 3.12")
    download_linux_python.main()
    shutil.copytree(download_linux_python.DESTINATION / "python", RUNTIME, symlinks=True)
    python = RUNTIME / "bin" / "python3.12"
    env = dict(os.environ, PYTHONUTF8="1", PIP_CACHE_DIR=str(CACHE / "pip"))
    run(str(python), "-m", "ensurepip", cwd=PROGRAM, env=env)

    step("Pinned application packages from manylinux wheels")
    pip = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:"]
    run(
        *pip,
        "-c",
        str(TOOLS / "constraints.txt"),
        "-r",
        str(TOOLS / "requirements.txt"),
        cwd=PROGRAM,
        env=env,
    )
    run(*pip, "--no-deps", "-r", str(TOOLS / "requirements-nodeps.txt"), cwd=PROGRAM, env=env)

    assets = json.loads((TOOLS / "build-assets.json").read_text(encoding="utf-8"))
    spacy = assets["spacy_model"]
    step(f"spaCy model ({spacy['name']} {spacy['version']})")
    wheel_name = f"{spacy['name']}-{spacy['version']}-py3-none-any.whl"
    wheel = CACHE / wheel_name
    download(
        f"https://github.com/explosion/spacy-models/releases/download/{spacy['name']}-{spacy['version']}/{wheel_name}",
        wheel,
        spacy["sha256"],
    )
    run(*pip, "--no-deps", "--force-reinstall", str(wheel), cwd=PROGRAM, env=env)

    step("Kokoro model and British voices")
    kokoro = assets["kokoro"]
    MODELS.mkdir(parents=True)
    model_download = CACHE / "kokoro-int8.onnx"
    download(
        f"{kokoro['repository']}/{kokoro['model']['path']}",
        model_download,
        kokoro["model"]["sha256"],
    )
    shutil.copyfile(model_download, MODELS / "kokoro-int8.onnx")
    voice_dir = CACHE / "kokoro-voices"
    for voice, voice_sha256 in kokoro["voices"].items():
        download(f"{kokoro['repository']}/voices/{voice}.bin", voice_dir / f"{voice}.bin", voice_sha256)
    run(str(python), str(TOOLS / "pack_kokoro_voices.py"), str(voice_dir), str(MODELS / "voices.npz"), env=env)

    step("Voice samples and native imports")
    sample_env = dict(env, PYTHONPATH=str(PROGRAM))
    run(str(python), str(TOOLS / "make_voice_samples.py"), str(MODELS), cwd=PROGRAM, env=sample_env)
    run(
        str(python),
        "-c",
        "import kokoro_onnx, lameenc, misaki.en, onnxruntime, spacy, ozvuchka; "
        f"assert spacy.util.is_package('{spacy['name']}'); print('  imports OK')",
        cwd=PROGRAM,
        env=env,
    )

    step("Remove build tools and user data")
    run(str(python), "-m", "pip", "uninstall", "--yes", "--disable-pip-version-check", "pip", cwd=PROGRAM, env=env)
    for executable in (RUNTIME / "bin").iterdir():
        if executable.name not in {"python", "python3", "python3.12"}:
            executable.unlink()
    for build_only in (
        RUNTIME / "include",
        RUNTIME / "lib" / "pkgconfig",
        RUNTIME / "lib" / "python3.12" / "ensurepip",
        RUNTIME / "lib" / "python3.12" / "test",
        RUNTIME / "share" / "man",
    ):
        shutil.rmtree(build_only, ignore_errors=True)
    shutil.rmtree(PROGRAM / "data", ignore_errors=True)
    for direct_url in RUNTIME.rglob("direct_url.json"):
        direct_url.unlink()

    step("Relocation-safe bytecode")
    run(
        str(python),
        "-m",
        "compileall",
        "-q",
        "-f",
        "-j",
        "0",
        "--invalidation-mode",
        "unchecked-hash",
        "runtime/lib/python3.12",
        "ozvuchka",
        cwd=PROGRAM,
        env=env,
    )

    copy_licenses()
    launcher = PROGRAM / f"{APP_NAME}.sh"
    launcher.write_text(LAUNCHER, encoding="utf-8", newline="\n")
    launcher.chmod(0o755)
    (PROGRAM / "version.txt").write_text(version, encoding="ascii")

    step("tar.gz")
    archive = DIST / f"ozvuchka-{version}-linux-x86_64.tar.gz"
    archive.unlink(missing_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(PROGRAM, arcname=APP_NAME)
    print(f"\nDone: {archive} ({archive.stat().st_size / 1024**2:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
