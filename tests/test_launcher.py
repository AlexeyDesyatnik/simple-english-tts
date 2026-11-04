"""The launcher's failure messages: the program's output before its log exists goes into data\\, and a data\\ folder
that cannot be written is said so. The real Ozvuchka.cs is compiled, with a stand-in for runtime\\pythonw.exe that
prints STUB_OUTPUT and exits with code 3."""

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "tools" / "launcher" / "Ozvuchka.cs"
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
STUB = """using System;
static class Stub
{
    static int Main()
    {
        string text = Environment.GetEnvironmentVariable("STUB_OUTPUT");
        if (!string.IsNullOrEmpty(text)) Console.Error.WriteLine(text);
        return 3;
    }
}
"""

pytestmark = pytest.mark.skipif(not CSC.exists(), reason="needs the C# compiler of .NET Framework 4 (Windows)")


@pytest.fixture
def program(tmp_path: Path) -> Path:
    stub = tmp_path / "stub.cs"
    stub.write_text(STUB, encoding="ascii")
    folder = tmp_path / "program"
    (folder / "runtime").mkdir(parents=True)
    _csc("exe", folder / "runtime" / "pythonw.exe", stub)
    _csc("winexe", folder / "Ozvuchka.exe", LAUNCHER, "/r:System.Windows.Forms.dll")
    return folder


def _csc(kind: str, target: Path, source: Path, *extra: str) -> None:
    subprocess.run(
        [str(CSC), "/nologo", f"/target:{kind}", "/codepage:65001", *extra, f"/out:{target}", str(source)],
        check=True,
        capture_output=True,
    )


def _start(folder: Path, output: str) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "STUB_OUTPUT": output}
    return subprocess.run([str(folder / "Ozvuchka.exe"), "--no-window"], capture_output=True, env=env, timeout=60)


def test_output_before_the_log_is_kept_in_data_and_named_in_the_message(program):
    result = _start(program, "startup boom")

    kept = program / "data" / "startup-output.txt"
    message = result.stderr.decode("utf-8-sig")
    assert result.returncode == 3
    assert kept.read_text(encoding="utf-8") == "startup boom\n"
    assert "startup-output.txt" in message
    assert "ozvuchka.log" not in message


def test_a_failure_with_no_output_says_so(program):
    result = _start(program, "")

    message = result.stderr.decode("utf-8-sig")
    assert result.returncode == 3
    assert not (program / "data" / "startup-output.txt").exists()
    assert "Подробностей об ошибке нет" in message
    assert "ozvuchka.log" not in message


def test_a_data_folder_that_cannot_be_written_is_reported_without_a_log(program):
    (program / "data").write_text("", encoding="utf-8")  # a file where the folder should be

    result = _start(program, "startup boom")

    message = result.stderr.decode("utf-8-sig")
    assert result.returncode == 3
    assert "Журнал не записан" in message
    assert "ozvuchka.log" not in message
    assert "startup-output.txt" not in message
