"""The Edge app window keeps its normal bounds and maximized state across restarts."""

import json
from dataclasses import replace

import pytest

import ozvuchka.window as window
from ozvuchka.window import WindowMonitor, WindowPlacement, WindowPlacementFile


class FakeWindows:
    def __init__(self, states=None):
        self.states = states or {}
        self.restored = []

    def windows(self):
        return list(self.states)

    def placement(self, handle):
        state = self.states.get(handle)
        return state if state is not None else None

    def set_placement(self, handle, placement):
        self.restored.append((handle, placement))
        self.states[handle] = (placement, False)


class CountingWindowPlacementFile(WindowPlacementFile):
    def __init__(self, data_dir):
        super().__init__(data_dir)
        self.writes = 0

    def save(self, placement):
        self.writes += 1
        super().save(placement)


def placement(maximized=False):
    return WindowPlacement(left=100, top=120, width=900, height=700, maximized=maximized)


def test_normal_window_placement_is_remembered_and_restored_after_a_restart(tmp_path):
    first_windows = FakeWindows({1: (placement(), False)})
    WindowMonitor(tmp_path, native=first_windows).check()

    second_windows = FakeWindows({2: (WindowPlacement(0, 0, 800, 600), False)})
    WindowMonitor(tmp_path, native=second_windows).check()

    assert second_windows.restored == [(2, placement())]


def test_a_maximized_window_restores_maximized_with_its_normal_bounds(tmp_path):
    WindowMonitor(tmp_path, native=FakeWindows({1: (placement(maximized=True), False)})).check()

    second_windows = FakeWindows({2: (WindowPlacement(0, 0, 800, 600), False)})
    WindowMonitor(tmp_path, native=second_windows).check()

    assert second_windows.restored == [(2, placement(maximized=True))]


def test_minimizing_does_not_replace_the_saved_maximized_state(tmp_path):
    native = FakeWindows({1: (placement(maximized=True), False)})
    monitor = WindowMonitor(tmp_path, native=native)
    monitor.check()
    native.states[1] = (replace(placement(), left=110, top=130), True)

    monitor.check()

    second_windows = FakeWindows({2: (WindowPlacement(0, 0, 800, 600), False)})
    WindowMonitor(tmp_path, native=second_windows).check()
    assert second_windows.restored == [(2, replace(placement(maximized=True), left=110, top=130))]


@pytest.mark.parametrize(
    "stored",
    [
        [],
        {"version": 99, "left": 100, "top": 120, "width": 900, "height": 700, "maximized": False},
        {"version": 1, "left": 100, "top": 120, "width": 0, "height": 700, "maximized": False},
        {"version": 1, "left": 100, "top": 120, "width": 900, "height": 700, "maximized": "no"},
    ],
)
def test_unusable_window_placement_gives_the_default(tmp_path, stored):
    (tmp_path / "window.json").write_text(json.dumps(stored), encoding="utf-8")

    native = FakeWindows({1: (WindowPlacement(0, 0, 800, 600), False)})
    WindowMonitor(tmp_path, native=native).check()

    assert native.restored == []
    assert WindowPlacementFile(tmp_path).read() == WindowPlacement(0, 0, 800, 600)


def test_an_unchanged_window_placement_is_not_written_again(tmp_path):
    files = CountingWindowPlacementFile(tmp_path)
    native = FakeWindows({1: (placement(), False)})
    monitor = WindowMonitor(tmp_path, native=native, files=files)

    monitor.check()
    monitor.check()

    assert files.writes == 1


def test_a_new_window_is_restored_only_once_then_the_user_can_move_it(tmp_path):
    WindowPlacementFile(tmp_path).save(placement())
    native = FakeWindows({1: (WindowPlacement(0, 0, 800, 600), False)})
    monitor = WindowMonitor(tmp_path, native=native)
    monitor.check()
    moved = WindowPlacement(250, 200, 1000, 750)
    native.states[1] = (moved, False)

    monitor.check()
    monitor.check()

    assert native.restored == [(1, placement())]
    assert WindowPlacementFile(tmp_path).read() == moved


def test_without_edge_the_default_browser_opens_as_before(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(window, "_find_edge", lambda: None)
    monkeypatch.setattr("ozvuchka.window.webbrowser.open", opened.append)

    window.open_window("http://127.0.0.1:8770")

    assert opened == ["http://127.0.0.1:8770"]
