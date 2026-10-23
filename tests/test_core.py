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
