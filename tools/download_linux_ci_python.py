"""Download and unpack the pinned baseline CPython used by the minimum-glibc CI container."""

import json
import shutil
import tarfile

from setup_linux import CACHE, TOOLS, download

DESTINATION = CACHE / "linux-ci-python"


def main() -> int:
    assets = json.loads((TOOLS / "build-assets.json").read_text(encoding="utf-8"))
    package = assets["linux_ci_python"]
    python = DESTINATION / "python" / "bin" / "python3.12"
    fingerprint = DESTINATION / "sha256"
    if python.exists() and fingerprint.exists() and fingerprint.read_text(encoding="ascii") == package["sha256"]:
        print(f"  cached: {python}")
        return 0

    archive = CACHE / "linux-ci-python.tar.gz"
    download(package["url"], archive, package["sha256"])
    partial = CACHE / "linux-ci-python.part"
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(partial, filter="data")
    (partial / "sha256").write_text(package["sha256"], encoding="ascii")
    shutil.rmtree(DESTINATION, ignore_errors=True)
    partial.replace(DESTINATION)
    print(f"  OK: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
