"""Startup: the program log is started before anything that loads native code, so an error there is kept in it."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module", ["ozvuchka.core", "ozvuchka.window"])
def test_an_error_while_loading_the_engine_is_written_to_the_log_of_the_program_folder(tmp_path, module):
    # __main__.py finds the program folder from its own place, so the copy in tmp_path uses tmp_path as its folder.
    main_copy = tmp_path / "ozvuchka" / "__main__.py"
    main_copy.parent.mkdir()
    shutil.copy(REPO / "ozvuchka" / "__main__.py", main_copy)
    script = (
        "import runpy, sys\n"
        f"sys.modules[{module!r}] = None  # a native dependency that fails to load\n"
        "sys.argv = ['ozvuchka', '--port', '8799']\n"
        f"runpy.run_path({str(main_copy)!r}, run_name='__main__')\n"
    )

    result = subprocess.run([sys.executable, "-c", script], cwd=REPO, capture_output=True, text=True, encoding="utf-8")

    log = tmp_path / "data" / "ozvuchka.log"
    assert result.returncode != 0
    assert log.exists(), f"no log written; stderr: {result.stderr}"
    text = log.read_text(encoding="utf-8")
    assert "Uncaught error" in text
    assert f"import of {module} halted" in text
