"""Exercise the shipped launcher with a tiny child process, without message boxes."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def launcher_files(tmp_path_factory):
    folder = tmp_path_factory.mktemp("launcher")
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    launcher = folder / "launcher.exe"
    subprocess.run([
        str(compiler), "-nologo", "-target:winexe", "-codepage:65001", "-r:System.Windows.Forms.dll",
        f"-out:{launcher}", str(Path("tools/launcher/Ozvuchka.cs")),
    ], check=True, capture_output=True)
    source = folder / "Child.cs"
    source.write_text('''using System;
using System.IO;
using System.Runtime.InteropServices;
class Child {
    [DllImport("kernel32.dll")] static extern IntPtr GetConsoleWindow();
    static int Main() {
        if (GetConsoleWindow() != IntPtr.Zero) return 99;
        string mode = File.ReadAllText("mode.txt");
        if (mode == "silent") return 23;
        Console.Out.WriteLine("current stdout");
        Console.Error.WriteLine("current stderr");
        return mode == "success" ? 0 : 17;
    }
}
''', encoding="utf-8")
    child = folder / "child.exe"
    subprocess.run([str(compiler), "-nologo", f"-out:{child}", str(source)], check=True, capture_output=True)
    return launcher, child


def launch(tmp_path, launcher_files, mode, blocked=False):
    launcher, child = launcher_files
    shutil.copyfile(launcher, tmp_path / "Озвучка.exe")
    (tmp_path / "runtime").mkdir()
    shutil.copyfile(child, tmp_path / "runtime" / "python.exe")
    (tmp_path / "mode.txt").write_text(mode, encoding="ascii")
    if blocked:
        (tmp_path / "data").write_text("blocked", encoding="ascii")
    else:
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "ozvuchka.log").write_text("stale failure", encoding="utf-8")
    return subprocess.run([str(tmp_path / "Озвучка.exe"), "--no-window"],
                          capture_output=True, text=True, encoding="utf-8", timeout=30)


def test_launcher_preserves_only_current_output_and_identifies_its_file(tmp_path, launcher_files):
    result = launch(tmp_path, launcher_files, "failure")
    assert result.returncode == 17
    assert "17" in result.stderr
    (diagnostic,) = (tmp_path / "data").glob("startup-*.log")
    assert diagnostic.name in result.stderr
    text = diagnostic.read_text(encoding="utf-8")
    assert "current stdout" in text
    assert "current stderr" in text
    assert "stale failure" not in text
    assert "ozvuchka.log" not in result.stderr


def test_launcher_reports_no_output_without_pointing_to_a_stale_log(tmp_path, launcher_files):
    result = launch(tmp_path, launcher_files, "silent")
    assert result.returncode == 23
    assert "23" in result.stderr
    assert "не вывел" in result.stderr
    assert "ozvuchka.log" not in result.stderr
    assert not list((tmp_path / "data").glob("startup-*.log"))


def test_launcher_explains_unwritable_diagnostics_without_claiming_a_file_exists(tmp_path, launcher_files):
    result = launch(tmp_path, launcher_files, "failure", blocked=True)
    assert result.returncode == 17
    assert "Не удалось сохранить" in result.stderr
    assert "доступна для записи" in result.stderr
    assert "Подробности —" not in result.stderr


def test_success_does_not_create_a_failure_diagnostic(tmp_path, launcher_files):
    result = launch(tmp_path, launcher_files, "success")
    assert result.returncode == 0
    assert result.stderr == ""
    assert not list((tmp_path / "data").glob("startup-*.log"))
