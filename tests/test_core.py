import json
import os
import threading
import time

import pytest

from ozvuchka.core import Core
from ozvuchka.voices import VoiceRegistry
from tests.fakes import FakeClock, FakeVoiceProvider


@pytest.fixture
def make_core(tmp_path):
    cores = []

    def make(provider, clock=None, computer="classroom-pc"):
        core = Core(
            VoiceRegistry([provider]),
            "fake:alice",
            clock=clock or FakeClock(),
            data_dir=tmp_path / "data",
            computer=computer,
        )
        cores.append((core, provider))
        return core

    yield make
    for core, provider in cores:
        provider.finish_all()  # a manual provider may still hold a piece the test did not need
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


def play_when_ready(core):
    """Presses Play and waits until the whole Narration is ready and playing."""
    core.play()
    wait_for(core, lambda s: all_ready(s) and s["playback"]["state"] == "playing")


TEXT_WITH_A_TASK = "Упражнение 1. Послушайте.\nTom has a cat.\nЗадание 2.\nThe cat is black.\nIt likes milk."


def test_paragraphs_play_in_order_skipping_skipped_paragraphs(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None, "start_delay": None}

    play_when_ready(core)
    assert playback(core) == {"state": "playing", "paragraph": 1, "next": 3, "start_delay": None}
    core.paragraph_started(1)
    core.paragraph_finished(1)
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}
    core.paragraph_started(3)
    core.paragraph_finished(3)
    core.paragraph_started(4)
    assert playback(core) == {"state": "playing", "paragraph": 4, "next": None, "start_delay": None}
    core.paragraph_finished(4)

    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None, "start_delay": None}


def test_the_page_can_start_the_next_paragraph_before_reporting_the_end_of_the_previous_one(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)

    core.paragraph_started(3)
    core.paragraph_finished(1)  # late: the position has already moved on

    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}


def test_a_text_with_nothing_to_read_does_not_start_playing(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text("Упражнение 1.\nПрочитайте текст.")

    core.play()

    assert playback(core)["state"] == "stopped"


def test_pause_keeps_the_position_and_play_resumes_it(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.paragraph_finished(1)

    core.pause()
    assert playback(core) == {"state": "paused", "paragraph": 3, "next": 4, "start_delay": None}
    core.paragraph_finished(3)  # the page may still report what was playing as it paused
    assert playback(core)["paragraph"] == 3

    core.play()
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}


def test_stop_returns_to_the_start_of_the_text(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.paragraph_finished(1)

    core.stop()
    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None, "start_delay": None}

    core.play()
    assert playback(core)["paragraph"] == 1


def test_a_new_text_stops_playback_but_the_same_text_again_changes_nothing(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.paragraph_finished(1)

    core.set_text(TEXT_WITH_A_TASK)
    assert playback(core)["paragraph"] == 3

    core.set_text("Another text.")
    assert playback(core)["state"] == "stopped"
    assert [p["text"] for p in core.snapshot()["text"]["paragraphs"]] == ["Another text."]


def test_next_and_previous_paragraph_play_the_neighbouring_one_passing_over_skipped_paragraphs(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)

    assert core.next_paragraph() is True
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}
    assert core.previous_paragraph() is True
    assert playback(core) == {"state": "playing", "paragraph": 1, "next": 3, "start_delay": None}


def test_previous_at_the_first_paragraph_and_next_at_the_last_leave_playback_as_it_is(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK + "\nУпражнение 3.")
    play_when_ready(core)

    assert core.previous_paragraph() is False
    assert playback(core) == {"state": "playing", "paragraph": 1, "next": 3, "start_delay": None}
    core.next_paragraph()
    core.next_paragraph()
    assert core.next_paragraph() is False
    assert playback(core) == {"state": "playing", "paragraph": 4, "next": None, "start_delay": None}


def test_repeat_plays_the_current_paragraph_again_even_when_paused(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.paragraph_finished(1)
    core.pause()

    assert core.repeat_paragraph() is True

    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}


def test_after_the_end_of_the_text_repeat_and_previous_go_back_from_the_last_paragraph(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.next_paragraph()
    core.next_paragraph()
    core.paragraph_finished(4)

    assert core.next_paragraph() is False
    assert playback(core)["state"] == "stopped"
    assert core.repeat_paragraph() is True
    assert playback(core) == {"state": "playing", "paragraph": 4, "next": None, "start_delay": None}
    core.paragraph_finished(4)
    assert core.previous_paragraph() is True
    assert playback(core) == {"state": "playing", "paragraph": 3, "next": 4, "start_delay": None}


def test_after_stop_next_plays_the_first_paragraph_while_previous_and_repeat_do_nothing(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)
    core.paragraph_finished(1)
    core.stop()

    assert core.previous_paragraph() is False
    assert core.repeat_paragraph() is False
    assert playback(core)["state"] == "stopped"
    assert core.next_paragraph() is True
    assert playback(core) == {"state": "playing", "paragraph": 1, "next": 3, "start_delay": None}


def test_next_previous_and_repeat_do_nothing_without_a_text(make_core):
    core = make_core(FakeVoiceProvider())

    assert (core.next_paragraph(), core.previous_paragraph(), core.repeat_paragraph()) == (False, False, False)
    assert playback(core)["state"] == "stopped"


def test_moving_to_a_paragraph_that_is_not_ready_synthesizes_it_next_and_waits_for_it(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text(TEXT_WITH_A_TASK)
    core.play()
    wait_for(core, lambda s: provider.requests == [("Tom has a cat.", "alice", 1.0)])

    core.next_paragraph()
    core.next_paragraph()

    assert playback(core)["state"] == "waiting"
    assert playback(core)["paragraph"] == 4
    provider.finish_next()
    wait_for(core, lambda s: len(provider.requests) == 2)
    assert provider.requests[1] == ("It likes milk.", "alice", 1.0)


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


# ---------------------------------------------------------------- Start delay


def lasting(seconds, letter="a"):
    """A one-word Paragraph the fake Voice provider says in this many seconds (0.1 s per character)."""
    return letter.upper() + letter * (round(seconds * 10) - 2) + "."


FOUR_PARAGRAPHS_OF_10_S = "\n".join(lasting(10, letter) for letter in "abcd")


def test_play_on_a_narration_slower_than_speech_waits_out_a_start_delay_that_counts_down(make_core):
    clock = FakeClock()
    provider = FakeVoiceProvider(manual=True, clock=clock, speed=0.5)
    core = make_core(provider, clock)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)

    core.play()
    assert playback(core) == {"state": "waiting", "paragraph": 0, "next": 1, "start_delay": None}  # not measured yet

    provider.finish_next()  # 20 s for 10 s of speech: this computer synthesizes at half the pace of speech
    snapshot = wait_for(core, lambda s: statuses(s)[0] == "ready")
    # Paragraph 1 is ready 23 s from now (20 s plus 15% to spare) and heard after 10 s; paragraph 2 at 46 s
    # and 20 s; paragraph 3 at 69 s and 30 s: playback can start in 39 s without ever waiting.
    assert snapshot["playback"]["state"] == "waiting"
    assert snapshot["playback"]["start_delay"] == pytest.approx(39)

    clock.advance(10)
    assert playback(core)["start_delay"] == pytest.approx(29)


def test_playback_starts_by_itself_before_synthesis_ends_and_never_reaches_a_paragraph_that_is_not_ready(make_core):
    clock = FakeClock(start=0)
    provider = FakeVoiceProvider(manual=True)  # the test moves the clock: each paragraph takes twice its length
    core = make_core(provider, clock)
    seconds = [4, 12, 6, 20, 8, 10]
    core.set_text("\n".join(lasting(s, letter) for s, letter in zip(seconds, "abcdef", strict=True)))
    core.play()

    ready_at, started_at = [], None
    for n, length in enumerate(seconds):
        wait_for(core, lambda s, n=n: statuses(s)[n] == "synthesizing")
        for _ in range(length * 4):  # half-second ticks, as the page polls
            clock.advance(0.5)
            if started_at is None and playback(core)["state"] == "playing":
                started_at = clock.now
        provider.finish_next()
        wait_for(core, lambda s, n=n: statuses(s)[n] == "ready")
        ready_at.append(clock.now)

    assert started_at is not None and started_at < ready_at[-1]
    heard_from = [started_at + sum(seconds[:n]) for n in range(len(seconds))]
    assert all(ready <= heard for ready, heard in zip(ready_at, heard_from, strict=True))


def test_on_a_computer_faster_than_speech_playback_starts_as_soon_as_the_first_paragraph_is_ready(make_core):
    clock = FakeClock()
    provider = FakeVoiceProvider(manual=True, clock=clock, speed=2)
    core = make_core(provider, clock)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)
    core.play()

    provider.finish_next()

    snapshot = wait_for(core, lambda s: statuses(s)[0] == "ready")
    assert statuses(snapshot)[1:] != ["ready"] * 3
    assert snapshot["playback"] == {"state": "playing", "paragraph": 0, "next": 1, "start_delay": None}


def test_the_start_delay_is_recalculated_when_synthesis_slows_down_along_the_way(make_core):
    clock = FakeClock()
    provider = FakeVoiceProvider(manual=True, clock=clock, speed=0.5)
    core = make_core(provider, clock)
    core.set_text("\n".join(lasting(10, letter) for letter in "abcde"))
    core.play()
    provider.finish_next()
    # 23 s of synthesis per paragraph: the last one is ready at 92 s and heard after 40 s.
    assert wait_for(core, lambda s: statuses(s)[0] == "ready")["playback"]["start_delay"] == pytest.approx(52)

    provider.speed = 0.25
    provider.finish_next()

    # 40 s for the second paragraph: synthesis is now counted at 34.5 s per paragraph (30 s, the average of
    # the two, plus 15%), so the last one is ready at 103.5 s and heard after 40 s.
    snapshot = wait_for(core, lambda s: statuses(s)[1] == "ready")
    assert snapshot["playback"]["start_delay"] == pytest.approx(63.5)


def measure_and_close(make_core, computer, speed, text):
    clock = FakeClock()
    core = make_core(FakeVoiceProvider(clock=clock, speed=speed), clock, computer=computer)
    core.set_text(text)
    core.play()
    wait_for(core, all_ready)
    core.close()


def start_delay_on(make_core, computer, text):
    """The Start delay right after Play on this computer, before anything is synthesized."""
    core = make_core(FakeVoiceProvider(manual=True), computer=computer)
    core.set_text(text)
    core.play()
    return playback(core)["start_delay"]


def test_the_synthesis_speed_is_remembered_separately_for_each_computer(make_core):
    measure_and_close(make_core, "celeron", 0.5, lasting(10, "a"))
    assert start_delay_on(make_core, "i5", lasting(10, "b")) is None  # never measured on this one
    measure_and_close(make_core, "i5", 2, lasting(10, "c"))

    two_paragraphs = lasting(10, "d") + "\n" + lasting(10, "e")
    # Celeron: 23 s per paragraph, the second heard after 10 s; i5: 5.75 s per paragraph.
    assert start_delay_on(make_core, "celeron", two_paragraphs) == pytest.approx(36)
    assert start_delay_on(make_core, "i5", two_paragraphs) == pytest.approx(5.75)


def test_a_ready_narration_does_not_start_playing_without_play(make_core):
    ready_and_close(make_core(FakeVoiceProvider()), FOUR_PARAGRAPHS_OF_10_S)
    clock = FakeClock()
    core = make_core(FakeVoiceProvider(), clock)

    core.open_text(core.snapshot()["library"][0]["id"])
    clock.advance(60)

    assert playback(core)["state"] == "stopped"


@pytest.mark.parametrize("command, state", [("stop", "stopped"), ("pause", "paused")])
def test_stop_or_pause_while_waiting_keeps_the_narration_from_starting_once_it_is_ready(make_core, command, state):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)
    core.play()

    getattr(core, command)()
    provider.finish_all()

    assert wait_for(core, all_ready)["playback"]["state"] == state


def said(provider):
    return [request[0][0] for request in provider.requests]  # the paragraphs' letters


def test_play_from_a_paragraph_that_is_not_ready_synthesizes_from_it_then_the_ones_before_it(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)

    core.play_from(2)
    assert playback(core)["paragraph"] == 2

    snapshot = wait_for(core, all_ready)
    assert said(provider) == ["C", "D", "A", "B"]
    assert snapshot["playback"] == {"state": "playing", "paragraph": 2, "next": 3, "start_delay": None}


def test_play_from_a_paragraph_while_another_is_synthesizing_switches_to_it_after_that_piece(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)
    core.play()
    wait_for(core, lambda s: statuses(s)[0] == "synthesizing")

    core.play_from(2)
    provider.finish_all()

    wait_for(core, all_ready)
    assert said(provider) == ["A", "C", "D", "B"]


def test_play_from_a_skipped_paragraph_is_rejected(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)

    with pytest.raises(ValueError):
        core.play_from(0)

    assert playback(core)["state"] == "stopped"


# ---------------------------------------------------------------- Narration queue


def queue_text(core, text):
    """Pastes a Text and queues its Narration, leaving it as the current Text."""
    core.new_text()
    core.set_text(text)
    core.enqueue()


def queued(snapshot):
    return [n["title"] for n in snapshot["queue"]]


def test_queued_narrations_are_synthesized_one_at_a_time_in_the_order_they_were_queued(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)

    queue_text(core, "Apple one.\nApple two.")
    queue_text(core, "Banana one.")

    snapshot = wait_for(core, lambda s: len(provider.requests) == 1)
    assert queued(snapshot) == ["Apple one. Apple two.", "Banana one."]
    assert snapshot["playback"]["state"] == "stopped"
    provider.finish_all()
    assert wait_for(core, lambda s: s["queue"] == [])["playback"]["state"] == "stopped"
    assert [r[0] for r in provider.requests] == ["Apple one.", "Apple two.", "Banana one."]


def test_play_moves_a_queued_narration_to_the_front_once_the_piece_under_way_is_done(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    queue_text(core, "Apple one.\nApple two.")
    queue_text(core, "Banana one.")
    queue_text(core, "Cherry one.\nCherry two.")
    wait_for(core, lambda s: len(provider.requests) == 1)

    core.play()

    assert queued(core.snapshot()) == ["Cherry one. Cherry two.", "Apple one. Apple two.", "Banana one."]
    provider.finish_all()
    wait_for(core, lambda s: s["queue"] == [])
    assert [r[0] for r in provider.requests] == [
        "Apple one.",
        "Cherry one.",
        "Cherry two.",
        "Apple two.",
        "Banana one.",
    ]


def test_a_cancelled_narration_keeps_the_pieces_already_synthesized_and_the_queue_moves_on(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    queue_text(core, "Apple one.\nApple two.\nApple three.")
    queue_text(core, "Banana one.")
    queue_text(core, "Cherry one.")
    apple, banana, _ = core.snapshot()["queue"]
    provider.finish_next()
    wait_for(core, lambda s: len(provider.requests) == 2)  # "Apple two." is under way

    core.cancel(banana["id"])
    core.cancel(apple["id"])

    assert queued(core.snapshot()) == ["Cherry one."]
    provider.finish_all()
    wait_for(core, lambda s: s["queue"] == [])
    assert [r[0] for r in provider.requests] == ["Apple one.", "Apple two.", "Cherry one."]
    core.open_text(apple["text_id"])
    assert statuses(core.snapshot()) == ["ready", "ready", "waiting"]


def test_cancelling_the_narration_waiting_to_play_stops_playback(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text(FOUR_PARAGRAPHS_OF_10_S)
    core.play()
    [narration] = wait_for(core, lambda s: len(provider.requests) == 1)["queue"]

    core.cancel(narration["id"])
    provider.finish_all()

    assert playback(core)["state"] == "stopped"
    assert core.snapshot()["queue"] == []
    assert len(provider.requests) == 1


def test_the_queue_shows_roughly_how_long_until_each_narration_is_ready(make_core):
    measure_and_close(make_core, "celeron", 0.5, lasting(10, "z"))
    clock = FakeClock()
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider, clock, computer="celeron")

    queue_text(core, lasting(10, "a"))
    queue_text(core, lasting(10, "b") + "\n" + lasting(10, "c"))

    # 23 s of synthesis per paragraph of 10 s (20 s plus 15% to spare): the first is ready in 23 s, the second
    # 46 s after it.
    snapshot = wait_for(core, lambda s: len(provider.requests) == 1)
    assert [n["ready_in"] for n in snapshot["queue"]] == pytest.approx([23, 69])
    clock.advance(10)
    assert [n["ready_in"] for n in core.snapshot()["queue"]] == pytest.approx([13, 59])


def test_the_time_left_is_unknown_until_the_synthesis_speed_is_measured(make_core):
    core = make_core(FakeVoiceProvider(manual=True))

    queue_text(core, lasting(10, "a"))

    assert [n["ready_in"] for n in core.snapshot()["queue"]] == [None]


def test_a_ready_narration_plays_while_another_one_is_synthesized(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text("Banana one.")
    core.play()
    provider.finish_next()
    banana = wait_for(core, all_ready)["text"]["id"]
    queue_text(core, "Apple one.\nApple two.")
    wait_for(core, lambda s: len(provider.requests) == 2)

    core.open_text(banana)
    core.play()

    snapshot = core.snapshot()
    assert snapshot["playback"]["state"] == "playing"
    assert queued(snapshot) == ["Apple one. Apple two."]
    provider.finish_all()
    wait_for(core, lambda s: s["queue"] == [])
    assert [r[0] for r in provider.requests] == ["Banana one.", "Apple one.", "Apple two."]


def test_a_narration_queued_before_a_restart_plays_after_it_without_synthesis(make_core):
    core = make_core(FakeVoiceProvider())
    queue_text(core, "Apple one.\nApple two.")
    core.new_text()
    wait_for(core, lambda s: s["queue"] == [])
    core.close()

    provider = FakeVoiceProvider()
    core = make_core(provider)
    core.open_text(core.snapshot()["library"][0]["id"])
    core.play()

    assert wait_for(core, all_ready)["playback"]["state"] == "playing"
    assert provider.requests == []


def test_the_queue_shows_which_narration_is_being_synthesized_until_the_piece_under_way_is_done(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    queue_text(core, "Apple one.\nApple two.")
    queue_text(core, "Banana one.")
    wait_for(core, lambda s: len(provider.requests) == 1)

    core.play()  # Banana moves to the front, but "Apple one." is still under way

    assert [(n["title"], n["synthesizing"]) for n in core.snapshot()["queue"]] == [
        ("Banana one.", False),
        ("Apple one. Apple two.", True),
    ]
    provider.finish_next()
    snapshot = wait_for(core, lambda s: len(provider.requests) == 2)
    assert [n["synthesizing"] for n in snapshot["queue"]] == [True, False]


def test_after_a_restart_in_the_middle_of_a_queued_narration_only_the_rest_is_synthesized(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    queue_text(core, "Apple one.\nApple two.\nApple three.")
    provider.finish_next()
    wait_for(core, lambda s: len(provider.requests) == 2)
    threading.Timer(0.05, provider.finish_next).start()  # the piece under way finishes as the program closes
    core.close()

    restarted = FakeVoiceProvider()
    core = make_core(restarted)
    core.open_text(core.snapshot()["library"][0]["id"])
    core.play()

    wait_for(core, all_ready)
    assert [r[0] for r in restarted.requests] == ["Apple three."]


# ---------------------------------------------------------------- Voice and Speed


def test_the_teacher_chooses_from_the_voices_by_their_labels_and_from_four_speeds_alice_at_normal_by_default(
    make_core,
):
    core = make_core(FakeVoiceProvider())

    snapshot = core.snapshot()

    assert [(v["id"], v["label"]) for v in snapshot["voices"]] == [
        ("fake:alice", "Alice — женский, британский"),
        ("fake:george", "George — мужской, британский"),
    ]
    assert snapshot["voice"] == "fake:alice"
    assert snapshot["speeds"] == [0.8, 0.9, 1.0, 1.1]
    assert snapshot["speed"] == 1.0


def test_one_text_in_two_voices_and_two_speeds_is_four_separate_narrations(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)
    core.set_text("Tom has a cat.")

    for voice, speed in [("fake:alice", 1.0), ("fake:george", 1.0), ("fake:george", 0.8), ("fake:alice", 0.8)]:
        core.set_voice(voice)
        core.set_speed(speed)
        assert statuses(core.snapshot()) == ["waiting"]
        core.play()
        wait_for(core, all_ready)

    assert provider.requests == [
        ("Tom has a cat.", "alice", 1.0),
        ("Tom has a cat.", "george", 1.0),
        ("Tom has a cat.", "george", 0.8),
        ("Tom has a cat.", "alice", 0.8),
    ]
    core.set_voice("fake:george")
    core.set_speed(1.0)
    snapshot = core.snapshot()
    assert statuses(snapshot) == ["ready"]
    assert core.audio(snapshot["text"]["paragraphs"][0]["audio"][0]).duration == pytest.approx(1.4)


def test_each_voice_and_speed_is_queued_as_a_narration_of_its_own(make_core):
    provider = FakeVoiceProvider(manual=True)
    core = make_core(provider)
    core.set_text("Tom has a cat.")

    core.enqueue()
    core.set_speed(0.9)
    core.enqueue()

    assert [(n["voice"], n["speed"]) for n in core.snapshot()["queue"]] == [("fake:alice", 1.0), ("fake:alice", 0.9)]
    provider.finish_all()
    wait_for(core, lambda s: s["queue"] == [])
    assert provider.requests == [("Tom has a cat.", "alice", 1.0), ("Tom has a cat.", "alice", 0.9)]


@pytest.mark.parametrize("command, value", [("set_voice", "fake:george"), ("set_speed", 0.8)])
def test_choosing_another_voice_or_speed_stops_the_narration_playing(make_core, command, value):
    core = make_core(FakeVoiceProvider())
    core.set_text(TEXT_WITH_A_TASK)
    play_when_ready(core)

    getattr(core, command)(value)

    assert playback(core) == {"state": "stopped", "paragraph": None, "next": None, "start_delay": None}


@pytest.mark.parametrize("command, value", [("set_voice", "fake:bob"), ("set_speed", 1.5)])
def test_a_voice_or_speed_not_on_offer_is_rejected(make_core, command, value):
    core = make_core(FakeVoiceProvider())

    with pytest.raises(ValueError):
        getattr(core, command)(value)

    assert (core.snapshot()["voice"], core.snapshot()["speed"]) == ("fake:alice", 1.0)


def test_the_last_voice_and_speed_chosen_are_remembered_after_a_restart(make_core):
    core = make_core(FakeVoiceProvider())
    core.set_voice("fake:george")
    core.set_speed(0.8)
    core.close()

    provider = FakeVoiceProvider()
    core = make_core(provider)
    snapshot = core.snapshot()
    assert (snapshot["voice"], snapshot["speed"]) == ("fake:george", 0.8)
    core.set_text("Hello.")
    core.play()
    wait_for(core, all_ready)
    assert provider.requests == [("Hello.", "george", 0.8)]


@pytest.mark.parametrize(
    "saved",
    [
        '{"version": 1, "voice": "fake:bob", "speed": 0.7}',  # a Voice no longer offered
        "{ not json",
        '{"version": 99, "voice": "fake:george", "speed": 0.8}',
    ],
)
def test_settings_that_cannot_be_used_give_the_default_voice_and_speed(make_core, tmp_path, saved):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "settings.json").write_text(saved, encoding="utf-8")

    core = make_core(FakeVoiceProvider())

    assert (core.snapshot()["voice"], core.snapshot()["speed"]) == ("fake:alice", 1.0)
    core.set_speed(0.9)
    core.close()
    assert make_core(FakeVoiceProvider()).snapshot()["speed"] == 0.9


def test_the_text_size_steps_through_seven_sizes_and_is_remembered_after_a_restart_with_the_voice(make_core):
    core = make_core(FakeVoiceProvider())
    assert core.snapshot()["text_sizes"] == [18, 22, 28, 36, 48, 64, 80]
    assert core.snapshot()["text_size"] == 22
    core.set_voice("fake:george")
    core.bigger_text()
    core.bigger_text()
    core.bigger_text()
    core.smaller_text()
    core.close()

    snapshot = make_core(FakeVoiceProvider()).snapshot()

    assert (snapshot["text_size"], snapshot["voice"]) == (36, "fake:george")


def test_the_text_size_stops_at_the_smallest_and_the_largest(make_core):
    core = make_core(FakeVoiceProvider())

    for _ in range(3):
        core.smaller_text()
    assert core.snapshot()["text_size"] == 18
    for _ in range(8):
        core.bigger_text()
    assert core.snapshot()["text_size"] == 80


def test_a_saved_text_size_not_on_offer_gives_the_default(make_core, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "settings.json").write_text('{"version": 1, "text_size": 100}', encoding="utf-8")

    assert make_core(FakeVoiceProvider()).snapshot()["text_size"] == 22


def test_the_start_delay_allows_for_the_speech_of_a_slower_speed_lasting_longer(make_core):
    two_paragraphs = lasting(10, "d") + "\n" + lasting(10, "e")

    measure_and_close(make_core, "celeron", 0.5, lasting(10, "a"))  # at Speed 1.0
    make_core(FakeVoiceProvider()).set_speed(0.8)
    # 23 s of synthesis per paragraph; the second is heard after 12.5 s at Speed 0.8.
    assert start_delay_on(make_core, "celeron", two_paragraphs) == pytest.approx(33.5)

    measure_and_close(make_core, "i5", 0.5, lasting(10, "b"))  # at Speed 0.8: 12.5 s of speech in 25 s
    make_core(FakeVoiceProvider()).set_speed(1.0)
    # 28.75 s of synthesis per paragraph; the second is heard after 10 s at Speed 1.0.
    assert start_delay_on(make_core, "i5", two_paragraphs) == pytest.approx(47.5)


def test_a_voice_sample_is_ready_to_play_without_synthesis(make_core):
    provider = FakeVoiceProvider()
    core = make_core(provider)

    sample = core.voice_sample("fake:george")

    assert sample is not None and sample.duration == pytest.approx(6)
    assert core.voice_sample("fake:bob") is None
    assert provider.requests == []
