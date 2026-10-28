"""The program log on a flash drive: it is rotated, so it never grows without limit."""

import logging
import sys
import threading

import pytest

from ozvuchka.log import start_log


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    hooks = sys.excepthook, threading.excepthook
    yield
    for handler in root.handlers:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)
    sys.excepthook, threading.excepthook = hooks


def test_the_log_keeps_the_newest_lines_and_two_older_parts_each_no_bigger_than_the_limit(tmp_path, restore_logging):
    start_log(tmp_path, max_bytes=1000)

    for line in range(100):
        logging.getLogger("ozvuchka").info("line %03d %s", line, "x" * 50)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["ozvuchka.log", "ozvuchka.log.1", "ozvuchka.log.2"]
    assert all(p.stat().st_size <= 1000 for p in tmp_path.iterdir())
    assert "line 099" in (tmp_path / "ozvuchka.log").read_text(encoding="utf-8")
    assert "line 000" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.iterdir())
