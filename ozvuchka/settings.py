"""The teacher's settings, the last Voice, Speed and Text size chosen, kept in the data folder, not the browser."""

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path

from ozvuchka.library import write_atomically

_FORMAT_VERSION = 1


@dataclass(frozen=True)
class Settings:
    voice: str | None = None  # a Voice key, "provider:voice"
    speed: float | None = None
    text_size: int | None = None  # pixels


class SettingsFile:
    def __init__(self, data_dir: Path):
        self._path = data_dir / "settings.json"

    def read(self) -> Settings:
        """The saved settings; empty ones if there are none or they cannot be read."""
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict) or stored.get("version") != _FORMAT_VERSION:
                return Settings()
            voice, speed, text_size = stored.get("voice"), stored.get("speed"), stored.get("text_size")
            return Settings(
                voice if isinstance(voice, str) else None,
                float(speed) if isinstance(speed, int | float) else None,
                text_size if isinstance(text_size, int) else None,
            )
        except (OSError, ValueError):
            return Settings()

    def save(self, settings: Settings) -> None:
        # Unlike the Library, a damaged file is overwritten: it holds nothing the teacher cannot choose again.
        stored = {
            "version": _FORMAT_VERSION,
            "voice": settings.voice,
            "speed": settings.speed,
            "text_size": settings.text_size,
        }
        with contextlib.suppress(OSError):  # without it the next start shows the defaults
            write_atomically(self._path, json.dumps(stored, ensure_ascii=False, indent=1).encode())
