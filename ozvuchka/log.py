"""The program log: data\\ozvuchka.log in the program folder (ADR-0001), and the console when there is one.

The log is rotated, so on a flash drive it never grows past three parts of MAX_BYTES each.
Started from Озвучка.exe the program has no console, so what Python or a library would print
to it, uncaught errors included, goes into the log as well.
"""

import io
import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "ozvuchka.log"
MAX_BYTES = 1_000_000
_OLD_PARTS = 2  # ozvuchka.log.1 and ozvuchka.log.2


def start_log(data_dir: Path, max_bytes: int = MAX_BYTES, *, console: bool = True) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    to_file = RotatingFileHandler(data_dir / LOG_NAME, maxBytes=max_bytes, backupCount=_OLD_PARTS, encoding="utf-8")
    handlers: list[logging.Handler] = [to_file]
    original_stderr = sys.stderr
    if not console or sys.stderr is None:
        # nobody would see an error of the log itself, and reporting it would print into the log again
        logging.raiseExceptions = False
        sys.stdout = sys.stderr = _ConsoleToLog()
    else:
        handlers.append(logging.StreamHandler())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)

    def uncaught(kind: type[BaseException], error: BaseException, tb: object) -> None:
        # The launcher needs evidence from this process even if the rotating log cannot be written later.
        if not console and original_stderr is not None:
            traceback.print_exception(error, file=original_stderr)
            original_stderr.flush()
        _log_uncaught(error)

    sys.excepthook = uncaught
    threading.excepthook = lambda args: _log_uncaught(args.exc_value or args.exc_type())


class _ConsoleToLog(io.TextIOBase):
    """Stands in for the missing console: each printed line becomes a line of the log. Writing to the log file
    directly would not do, since rotation replaces it."""

    def __init__(self) -> None:
        self._line = ""
        self._lock = threading.Lock()

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        with self._lock:
            *lines, self._line = (self._line + text).split("\n")
        for line in lines:
            logging.getLogger("ozvuchka.printed").warning("%s", line)
        return len(text)


def _log_uncaught(error: BaseException) -> None:
    logging.getLogger("ozvuchka").critical("Uncaught error", exc_info=error)
