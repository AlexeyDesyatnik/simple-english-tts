"""Startup failures are diagnosed before application dependencies can load."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def program(tmp_path):
    package = tmp_path / "ozvuchka"
    package.mkdir()
    for name in ("__init__.py", "__main__.py", "log.py", "window.py"):
        shutil.copyfile(Path("ozvuchka") / name, package / name)
    (package / "core.py").write_text("raise ImportError('early dependency failure')\n", encoding="utf-8")
    return tmp_path


def run_program(program):
    # The embeddable runtime ignores cwd on sys.path; explicitly select the isolated program.
    code = "import sys, runpy; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module('ozvuchka', run_name='__main__')"
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code, str(program)],
        env={**os.environ, "OZVUCHKA_LAUNCHER": "1"}, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def test_an_early_dependency_exception_is_in_the_log_and_current_launch_output(program):
    result = run_program(program)
    assert result.returncode != 0
    log = (program / "data" / "ozvuchka.log").read_text(encoding="utf-8")
    assert "Traceback (most recent call last)" in log
    assert "ImportError: early dependency failure" in log
    assert "ImportError: early dependency failure" in result.stderr
    assert " INFO " not in result.stderr


def test_unavailable_log_storage_leaves_the_exception_in_current_launch_output(program):
    (program / "data").write_text("not a directory", encoding="utf-8")
    result = run_program(program)
    assert result.returncode != 0
    assert "Traceback (most recent call last)" in result.stderr
    assert "FileExistsError" in result.stderr
    assert "early dependency failure" not in result.stderr


def test_an_unwritable_log_in_existing_data_leaves_the_exception_in_current_launch_output(program):
    (program / "data" / "ozvuchka.log").mkdir(parents=True)
    result = run_program(program)
    assert result.returncode != 0
    assert "Traceback (most recent call last)" in result.stderr
    assert "PermissionError" in result.stderr
    assert "early dependency failure" not in result.stderr
