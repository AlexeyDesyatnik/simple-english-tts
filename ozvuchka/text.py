"""Text preparation: a Text becomes Paragraphs, and each Paragraph becomes the pieces to synthesize."""

import re
from dataclasses import dataclass

from num2words import num2words

# Rules ported from the prototype (english-speaking-prototype, ttscore/text.py), where they were debugged
# by ear: misaki reads times and ranges badly, so they are turned into words beforehand.
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_RANGE_RE = re.compile(r"\b(\d+)\s?[-–—]\s?(\d+)\b")

# Sentences are split without breaking dialogue ("What...?" asks her grandmother. is one sentence)
# and not at abbreviations or initials. A candidate end of a sentence: the mark, maybe a closing
# quote or bracket, a space, then a capital letter, a digit or an opening quote.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "st", "mt", "jr", "sr", "vs", "etc", "no",
    "e.g", "i.e", "a.m", "p.m", "approx", "dept", "fig", "ex", "p", "pp",
}  # fmt: skip
_BOUNDARY_RE = re.compile(r'[.!?…]+["”’)\]]*\s+(?=["“‘(\[]?[A-Z0-9])')
_LAST_WORD_RE = re.compile(r"(?:^|[\s(\"“])([A-Za-z][A-Za-z.]*)\.$")

# Kokoro reads up to about 510 phonemes and rushes on long input, so a longer paragraph
# is synthesized in pieces.
_MAX_PIECE = 400

_LATIN_RE = re.compile(r"[A-Za-z]")
_CYRILLIC_WORD_RE = re.compile(r"[А-Яа-яЁё]+(?:[-'’][А-Яа-яЁё]+)*")
# What cutting out the Russian words leaves behind: empty brackets, a dash or colon
# with nothing after it, punctuation at the start or doubled.
_EMPTY_BRACKETS_RE = re.compile(r"\(\W*\)|«\W*»|\[\W*\]")
_DANGLING_RE = re.compile(r"\s*[—–:;,-]+\s*(?=[.!?…]|$)")
_LEADING_RE = re.compile(r"^[\s—–\-:;,.!?…]+")
_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([.,!?;:…])")
_DOUBLED_RE = re.compile(r"([.!?…])(?:\s*[,;:]|\s+\.)+")  # ". ." but not "..."
_SPACES_RE = re.compile(r"[ \t ]+")


@dataclass(frozen=True)
class Paragraph:
    text: str  # the line as the teacher sees it
    pieces: tuple[str, ...]  # prepared text, one synthesis each; empty for a Skipped paragraph

    @property
    def skipped(self) -> bool:
        return not self.pieces


def paragraphs(text: str) -> list[Paragraph]:
    """Every non-empty line is a Paragraph."""
    return [_paragraph(line) for line in (raw.strip() for raw in text.splitlines()) if line]


def _paragraph(line: str) -> Paragraph:
    if not _LATIN_RE.search(line):
        return Paragraph(line, ())  # a Skipped paragraph: no English in it
    return Paragraph(line, _pieces(_normalized(_without_cyrillic(line))))


def _pieces(paragraph: str) -> tuple[str, ...]:
    """Splits a long paragraph at sentence boundaries into roughly equal pieces of at most about _MAX_PIECE."""
    count = -(-len(paragraph) // _MAX_PIECE)
    if count <= 1:
        return (paragraph,)
    groups: list[list[str]] = [[] for _ in range(count)]
    position = 0
    for sentence in _sentences(paragraph):
        middle = position + len(sentence) / 2  # a sentence goes to the piece its middle falls into
        groups[min(int(middle / len(paragraph) * count), count - 1)].append(sentence)
        position += len(sentence) + 1
    return tuple(" ".join(group) for group in groups if group)


def _sentences(paragraph: str) -> list[str]:
    result, start = [], 0
    for m in _BOUNDARY_RE.finditer(paragraph):
        before = paragraph[start : m.start() + 1]
        last = _LAST_WORD_RE.findall(before.rstrip())
        if last:
            word = last[0]
            if word.lower().rstrip(".") in _ABBREVIATIONS:
                continue  # "Mr. Brown" is not the end of a sentence
            if len(word) == 1 and word.isupper() and word != "I":
                continue  # initials: "J. K. Rowling"
        result.append(paragraph[start : m.end()].strip())
        start = m.end()
    tail = paragraph[start:].strip()
    if tail:
        result.append(tail)
    return result


def _time(m: re.Match[str]) -> str:
    h, mm = int(m.group(1)), int(m.group(2))
    if mm == 0:
        return f"{num2words(h)} o'clock"
    if mm < 10:
        return f"{num2words(h)} oh {num2words(mm)}"
    return f"{num2words(h)} {num2words(mm)}"


def _normalized(text: str) -> str:
    text = _TIME_RE.sub(_time, text)
    text = _RANGE_RE.sub(lambda m: f"{m.group(1)} to {m.group(2)}", text)
    return _SPACES_RE.sub(" ", text).strip()


def _without_cyrillic(line: str) -> str:
    if not _CYRILLIC_WORD_RE.search(line):
        return line
    text = _CYRILLIC_WORD_RE.sub("", line)
    text = _EMPTY_BRACKETS_RE.sub("", text)
    text = _SPACES_RE.sub(" ", text)
    text = _DANGLING_RE.sub("", text)
    text = _LEADING_RE.sub("", text)
    text = _DOUBLED_RE.sub(r"\1", text)
    text = _SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", text)
    return text.strip()
