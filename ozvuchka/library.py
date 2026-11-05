"""The Library on disk (ADR-0001): the Texts in one versioned JSON file, every Narration piece in a file of its own.

Every write goes to a temporary file that is then renamed over the old one, so a crash or a pulled-out
flash drive leaves either the old file or the new one, never half of one.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ozvuchka.audio import Audio, audio_from_wav

_FORMAT_VERSION = 1


@dataclass(frozen=True)
class SavedText:
    id: str
    content: str
    title: str | None = None


class LibraryFiles:
    def __init__(self, data_dir: Path):
        self._texts = data_dir / "library.json"
        self._pieces = data_dir / "narrations"
        self._pieces.mkdir(parents=True, exist_ok=True)

    def texts(self) -> list[SavedText]:
        """The saved Texts, most recently used first. Raises ValueError for a damaged file or a newer format."""
        if not self._texts.exists():
            return []
        stored = json.loads(self._texts.read_text(encoding="utf-8"))
        if (
            not isinstance(stored, dict)
            or type(stored.get("version")) is not int
            or stored["version"] != _FORMAT_VERSION
            or not isinstance(stored.get("texts"), list)
        ):
            raise ValueError("the file is damaged or saved by a newer version of the program")
        texts: list[SavedText] = []
        ids: set[str] = set()
        for record in stored["texts"]:
            if not isinstance(record, dict):
                raise ValueError("a Text record is damaged")
            text_id, content, title = record.get("id"), record.get("content"), record.get("title")
            if (
                not isinstance(text_id, str) or not text_id or text_id in ids
                or not isinstance(content, str)
                or (title is not None and not isinstance(title, str))
            ):
                raise ValueError("a Text record is damaged")
            ids.add(text_id)
            texts.append(SavedText(text_id, content, title))
        return texts

    def save_texts(self, texts: list[SavedText]) -> None:
        stored = {
            "version": _FORMAT_VERSION,
            "texts": [
                {"id": t.id, "content": t.content, **({"title": t.title} if t.title is not None else {})}
                for t in texts
            ],
        }
        write_atomically(self._texts, json.dumps(stored, ensure_ascii=False, indent=1).encode())

    def size(self) -> int:
        """Bytes taken by the saved Texts and Narration pieces."""
        texts = self._texts.stat().st_size if self._texts.exists() else 0
        return texts + sum(path.stat().st_size for path in self._pieces.glob("*.wav"))

    def pieces(self) -> set[str]:
        """The audio ids of the Narration pieces already saved."""
        return {path.stem for path in self._pieces.glob("*.wav")}

    def save_piece(self, audio_id: str, audio: Audio) -> None:
        # Core rejects unsupported provider output before it reaches persistence.
        assert audio.format == "wav"
        write_atomically(self._pieces / f"{audio_id}.wav", audio.data)

    def piece(self, audio_id: str) -> Audio:
        return audio_from_wav((self._pieces / f"{audio_id}.wav").read_bytes())

    def delete_piece(self, audio_id: str) -> None:
        (self._pieces / f"{audio_id}.wav").unlink(missing_ok=True)


def write_atomically(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
