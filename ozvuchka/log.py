"""The program log: data\\ozvuchka.log in the program folder (ADR-0001), and the console when there is one.

Started from Озвучка.exe the program has no console (pythonw.exe), so what Python or a library would print
to it, uncaught errors included, goes into the log as well.
"""

import logging
import sys
import threading
from pathlib import Path

LOG_NAME = "ozvuchka.log"


def start_log(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    to_file = logging.FileHandler(data_dir / LOG_NAME, encoding="utf-8")
    handlers: list[logging.Handler] = [to_file]
    if sys.stderr is None:
        sys.stdout = sys.stderr = to_file.stream
    else:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)
    sys.excepthook = lambda kind, error, traceback: _log_uncaught(error)
    threading.excepthook = lambda args: _log_uncaught(args.exc_value or args.exc_type())


def _log_uncaught(error: BaseException) -> None:
    logging.getLogger("ozvuchka").critical("Uncaught error", exc_info=error)
