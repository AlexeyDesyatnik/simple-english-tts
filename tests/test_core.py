import json
import os
import time

import pytest

from ozvuchka.core import Core
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeClock, FakeVoiceProvider


@pytest.fixture
def make_core(tmp_path):
    cores = []

    def make(provider):
        core = Core(VoiceRegistry([provider]), "fake:alice", clock=FakeClock(), data_dir=tmp_path / "data")
        cores.append(core)
        return core

    yield make
    for core in cores:
        core.close()


def wait_for(core, condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = core.snapshot()
        if condition(snapshot):
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"condition not reached; last snapshot: {core.snapshot()}")


def all_ready(snapshot):
    return all(p["status"] in ("ready", "skipped") for p in snapshot["text"]["paragraphs"])


def statuses(snapshot):
    return [p["status"] for p in snapshot["text"]["paragraphs"]]


# ---------------------------------------------------------------- synthesis


def test_after_play_every_paragraph_becomes_playable_audio_in_the_default_voice(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)

    core.set_text("Hello, class.\n\nToday we read a story.\n")
    core.play()

    snapshot = wait_for(core, all_ready)
    assert [p["text"] for p in snapshot["text"]["paragraphs"]] == ["Hello, class.", "Today we read a story."]
    assert provider.requests == [("Hello, class.", "alice", 1.0), ("Today we read a story.", "alice", 1.0)]
    first, second = (p["audio"] for p in snapshot["text"]["paragraphs"])
    assert core.audio(first[0]).duration == pytest.approx(1.3)
    assert core.audio(second[0]).duration == pytest.approx(2.2)


def test_synthesis_waits_for_play_then_goes_one_paragraph_at_a_time(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text("One.\nTwo.")
    time.sleep(0.05)
    assert provider.requests == []

    core.play()

    snapshot = wait_for(core, lambda s: statuses(s) == ["synthesizing", "waiting"])
    assert [p["audio"] for p in snapshot["text"]["paragraphs"]] == [None, None]
    provider.finish_next()
    wait_for(core, lambda s: statuses(s) == ["ready", "synthesizing"])
    provider.finish_next()
    wait_for(core, all_ready)


# ---------------------------------------------------------------- text preparation


@pytest.fixture
def spoken(make_core):
    """What the Voice provider is asked to say for a Text, piece by piece."""

    def speak(text):
        provider = FakeVoiceProvider()
        core = make_core(provider)
        core.set_text(text)
        core.play()
        wait_for(core, all_ready)
        return [request[0] for request in provider.requests]

    return speak


def test_a_russian_paragraph_is_shown_but_skipped(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)

    core.set_text("Упражнение 3. Прочитайте текст.\nTom has a cat.")
    core.play()

    snapshot = wait_for(core, all_ready)
    russian = snapshot["text"]["paragraphs"][0]
    assert russian["text"] == "Упражнение 3. Прочитайте текст."
    assert russian["status"] == "skipped"
    assert provider.requests == [("Tom has a cat.", "alice", 1.0)]


@pytest.mark.parametrize(
    "paragraph, said",
    [
        ("Прочитайте и переведите: Tom has a cat.", "Tom has a cat."),
        ("Tom (Том) has a cat.", "Tom has a cat."),
        ("Tom has a cat — у Тома есть кошка.", "Tom has a cat."),
        ("1. Прочитайте. Read the text.", "1. Read the text."),
        ("Слушайте: Wait... what?", "Wait... what?"),
    ],
)
def test_cyrillic_is_cut_out_of_a_mixed_paragraph(spoken, paragraph, said):
    assert spoken(paragraph) == [said]


@pytest.mark.parametrize(
    "paragraph, said",
    [
        ("The lesson starts at 8:30.", "The lesson starts at eight thirty."),
        ("We meet at 9:05 or 10:00.", "We meet at nine oh five or ten o'clock."),
        ("Read pages 10-12.", "Read pages 10 to 12."),
        ("Do exercises 3 – 5.", "Do exercises 3 to 5."),
    ],
)
def test_times_and_ranges_are_said_in_words(spoken, paragraph, said):
    assert spoken(paragraph) == [said]


def filler(count):
    """Distinct sentences of 41 characters each, joined by spaces."""
    return " ".join(f"Tom reads a book in the garden on day {day:02}." for day in range(1, count + 1))


def test_a_long_paragraph_is_synthesized_in_roughly_equal_pieces_but_stays_one_paragraph(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)
    paragraph = filler(24)  # 1007 characters

    core.set_text(paragraph)
    core.play()

    snapshot = wait_for(core, all_ready)
    pieces = [request[0] for request in provider.requests]
    assert len(pieces) == 3
    assert " ".join(pieces) == paragraph
    assert all(piece.endswith(".") for piece in pieces)
    assert max(map(len, pieces)) < 1.3 * min(map(len, pieces))
    [only] = snapshot["text"]["paragraphs"]
    assert only["text"] == paragraph
    assert len(only["audio"]) == 3


def test_a_paragraph_of_about_400_characters_is_one_piece(spoken):
    paragraph = filler(9)  # 377 characters

    assert spoken(paragraph) == [paragraph]


@pytest.mark.parametrize(
    "sentence",
    [
        '"What is this?" asks her grandmother.',
        '"What…?" asks her grandmother.',
        "Mr. Brown is our teacher.",
        "Dr. Smith comes at five.",
        "J. K. Rowling wrote it.",
    ],
)
def test_a_long_paragraph_is_not_split_inside_dialogue_an_abbreviation_or_initials(spoken, sentence):
    # The sentence sits right in the middle of the paragraph, where the split would go.
    paragraph = f"{filler(5)} {sentence} {filler(5)}"

    pieces = spoken(paragraph)

    assert len(pieces) == 2
    assert " ".join(pieces) == paragraph
    assert any(sentence in piece for piece in pieces)


# ---------------------------------------------------------------- playback


def playback(core):
    return core.snapshot()["playback"]


TEXT_WITH_A_TASK = "Упражнение 1. Послушайте.\nTom has a cat.\nЗадание 2.\nThe cat is black.\nIt likes milk."


def test_paragraphs_play_in_order_skipping_skipped_paragraphs(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None}

    core.play()
    assert playback(core) == {"state": "playing", "paragraph": 1, "next": 3}
    core.paragraph_started(1)
    core.paragraph_finished(1)
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4}
    core.paragraph_started(3)
    core.paragraph_finished(3)
    core.paragraph_started(4)
    assert playback(core) == {"state": "playing", "paragraph": 4, "next": None}
    core.paragraph_finished(4)

    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None}


def test_the_page_can_start_the_next_paragraph_before_reporting_the_end_of_the_previous_one(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    core.play()

    core.paragraph_started(3)
    core.paragraph_finished(1)  # late: the position has already moved on

    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4}


def test_a_text_with_nothing_to_read_does_not_start_playing(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text("Упражнение 1.\nПрочитайте текст.")

    core.play()

    assert playback(core)["state"] == "stopped"


def test_pause_keeps_the_position_and_play_resumes_it(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    core.play()
    core.paragraph_finished(1)

    core.pause()
    assert playback(core) == {"state": "paused", "paragraph": 3, "next": 4}
    core.paragraph_finished(3)  # the page may still report what was playing as it paused
    assert playback(core)["paragraph"] == 3

    core.play()
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4}


def test_stop_returns_to_the_start_of_the_text(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    core.play()
    core.paragraph_finished(1)

    core.stop()
    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None}

    core.play()
    assert playback(core)["paragraph"] == 1


def test_a_new_text_stops_playback_but_the_same_text_again_changes_nothing(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    core.play()
    core.paragraph_finished(1)

    core.set_text(TEXT_WITH_A_TASK)
    assert playback(core)["paragraph"] == 3

    core.set_text("Another text.")
    assert playback(core)["state"] == "stopped"
    assert [p["text"] for p in core.snapshot()["text"]["paragraphs"]] == ["Another text."]


def test_play_without_a_text_is_rejected(make_core):
    core = make_core(FakeVoiceProvider())

    with pytest.raises(ValueError):
        core.play()

    assert core.snapshot()["text"] is None


def test_a_paragraph_fails_visibly_when_the_voice_provider_is_unavailable(make_core):
    provider = FakeVoiceProvider(available=False)
    core = make_core(provider)
    core.set_text("Hello.")

    core.play()

    snapshot = wait_for(core, lambda s: statuses(s) == ["failed"])
    assert "Alice" in snapshot["text"]["paragraphs"][0]["error"]
    assert snapshot["text"]["paragraphs"][0]["audio"] is None
    assert snapshot["voices"][0]["available"] is False


def test_play_again_retries_a_failed_paragraph(make_core):
    provider = FakeVoiceProvider(available=False)
    core = make_core(provider)
    core.set_text("Hello.")
    core.play()
    wait_for(core, lambda s: statuses(s) == ["failed"])

    provider.set_available(True)
    core.play()

    wait_for(core, all_ready)


def test_the_snapshot_gives_back_the_text_as_pasted_so_a_reloaded_page_can_show_it(make_core):
    core = make_core(FakeVoiceProvider())

    core.set_text("Hello.\r\n\r\nУпражнение 2.\r\n")

    assert core.snapshot()["text"]["content"] == "Hello.\r\n\r\nУпражнение 2.\r\n"


# ---------------------------------------------------------------- the Library


def ready_and_close(core, text):
    core.set_text(text)
    core.play()
    wait_for(core, all_ready)
    core.close()


def test_after_a_restart_a_saved_text_opens_from_the_library_and_plays_without_synthesis(make_core):
    ready_and_close(make_core(FakeVoiceProvider()), "Tom has a cat.\nThe cat is black.")

    provider = FakeVoiceProvider()
    core = make_core(provider)
    [saved] = core.snapshot()["library"]
    assert saved["title"] == "Tom has a cat. The…"
    core.open_text(saved["id"])
    core.play()

    snapshot = wait_for(core, all_ready)
    assert snapshot["text"]["content"] == "Tom has a cat.\nThe cat is black."
    assert snapshot["playback"]["state"] == "playing"
    assert core.audio(snapshot["text"]["paragraphs"][1]["audio"][0]).duration == pytest.approx(1.7)
    assert provider.requests == []


FIVE_PARAGRAPHS = "One fish.\nTwo fish.\nRed fish.\nBlue fish.\nOld fish."


def test_editing_one_paragraph_of_five_resynthesizes_only_it_and_updates_the_same_text(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)
    core.set_text(FIVE_PARAGRAPHS)
    core.play()
    wait_for(core, all_ready)
    provider.requests.clear()

    core.set_text("One fish.\nTwo fish.\nGreen fish.\nBlue fish.\nOld fish.")
    core.play()

    wait_for(core, all_ready)
    assert provider.requests == [("Green fish.", "alice", 1.0)]
    assert [t["title"] for t in core.snapshot()["library"]] == ["One fish. Two fish. Green…"]


def test_identical_pieces_are_synthesized_once(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)

    core.set_text("Repeat after me.\nHello.\nRepeat after me.")
    core.play()

    wait_for(core, all_ready)
    assert provider.requests == [("Repeat after me.", "alice", 1.0), ("Hello.", "alice", 1.0)]


def test_the_library_lists_texts_by_last_use(make_core):
    core = make_core(FakeVoiceProvider())
    for text in ["First text.", "Second text.", "Third text."]:
        core.new_text()
        core.set_text(text)
    first = core.snapshot()["library"][2]

    core.open_text(first["id"])

    snapshot = core.snapshot()
    assert [t["title"] for t in snapshot["library"]] == ["First text.", "Third text.", "Second text."]
    assert snapshot["text"]["content"] == "First text."
    core.close()
    assert [t["title"] for t in make_core(FakeVoiceProvider()).snapshot()["library"]] == [
        "First text.",
        "Third text.",
        "Second text.",
    ]


def test_a_new_text_leaves_the_current_one_in_the_library(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text("First text.")

    core.new_text()

    snapshot = core.snapshot()
    assert snapshot["text"] is None
    assert [t["title"] for t in snapshot["library"]] == ["First text."]


def test_opening_a_text_that_is_not_in_the_library_is_rejected(make_core):
    core = make_core(FakeVoiceProvider())

    with pytest.raises(ValueError):
        core.open_text("nonexistent")


def crash_on_every_rename(monkeypatch):
    """From now on every write stops just before its rename, as if the program were killed there."""

    def crash(source, destination):
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "replace", crash)


def test_a_crash_while_synthesizing_keeps_the_pieces_already_finished(make_core, monkeypatch):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text("Tom has a cat.\nThe cat is black.\nIt likes milk.")
    core.play()
    provider.finish_next()
    wait_for(core, lambda s: statuses(s) == ["ready", "synthesizing", "waiting"])

    crash_on_every_rename(monkeypatch)
    provider.finish_next()
    provider.finish_next()
    wait_for(core, all_ready)  # they still play, but were never saved
    monkeypatch.undo()
    core.close()

    restarted = FakeVoiceProvider()
    core = make_core(restarted)
    core.open_text(core.snapshot()["library"][0]["id"])
    core.play()
    wait_for(core, all_ready)
    assert restarted.requests == [("The cat is black.", "alice", 1.0), ("It likes milk.", "alice", 1.0)]


def test_a_crash_while_saving_the_library_leaves_the_previous_version_readable(make_core, monkeypatch):
    core = make_core(FakeVoiceProvider())
    core.set_text("Tom has a cat.")

    crash_on_every_rename(monkeypatch)
    core.set_text("Tom has a dog.")
    assert core.snapshot()["library_error"].startswith("Не удалось сохранить Библиотеку")
    monkeypatch.undo()
    core.close()

    [saved] = make_core(FakeVoiceProvider()).snapshot()["library"]
    assert saved["title"] == "Tom has a cat."


def test_every_save_records_the_data_format_version(make_core, tmp_path):
    core = make_core(FakeVoiceProvider())

    core.set_text("Tom has a cat.")

    assert json.loads((tmp_path / "data" / "library.json").read_text(encoding="utf-8"))["version"] == 1


@pytest.mark.parametrize("damaged", ["{ not json", '{"version": 99, "texts": []}'])
def test_an_unreadable_library_is_reported_and_left_untouched_while_the_program_still_works(
    make_core, tmp_path, damaged
):
    library = tmp_path / "data" / "library.json"
    library.parent.mkdir(parents=True)
    library.write_text(damaged, encoding="utf-8")
    core = make_core(FakeVoiceProvider())

    core.set_text("Tom has a cat.")
    core.play()

    snapshot = wait_for(core, all_ready)
    assert snapshot["library_error"].startswith("Не удалось прочитать Библиотеку")
    assert library.read_text(encoding="utf-8") == damaged
