"""A Linux per-port flock whose lifetime is tied to the owning process."""

import contextlib
import fcntl
from pathlib import Path
from typing import Any, BinaryIO

_fcntl: Any = fcntl  # POSIX-only fcntl names are absent from Windows type stubs.


class PosixPortLock:
    def __init__(self, port: int, data_dir: Path):
        self._path = data_dir / f"instance-{port}.lock"
        self._file: BinaryIO | None = None

    def acquire(self) -> bool:
        if self._file is None:
            self._file = self._path.open("ab")
        try:
            _fcntl.flock(self._file.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def close(self) -> None:
        if self._file is None:
            return
        with contextlib.suppress(OSError):
            _fcntl.flock(self._file.fileno(), _fcntl.LOCK_UN)
        self._file.close()
        self._file = None
