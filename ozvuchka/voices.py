"""Voices and Voice providers.

A Voice provider is anything with the VoiceProvider shape; the registry holds them all.
A Voice is identified by the pair "provider + voice", written as "provider:voice".
"""

from dataclasses import dataclass
from typing import Protocol

from ozvuchka.audio import Audio


@dataclass(frozen=True)
class Voice:
    provider: str
    id: str
    label: str  # Russian, for the teacher: "Alice — женский, британский"
    gender: str  # "female" | "male"
    accent: str  # "gb" | "us"

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.id}"


class VoiceProvider(Protocol):
    id: str

    def voices(self) -> list[Voice]: ...

    def available(self) -> bool:
        """Whether the provider can synthesize right now (model loaded, connection up)."""
        ...

    def synthesize(self, text: str, voice: str, speed: float) -> Audio:
        """Synthesizes one piece of text with one of this provider's Voices at a Speed."""
        ...


class VoiceRegistry:
    def __init__(self, providers: list[VoiceProvider]):
        self._providers = {p.id: p for p in providers}

    def voices(self) -> list[Voice]:
        return [v for p in self._providers.values() for v in p.voices()]

    def voice(self, key: str) -> Voice:
        return next(v for v in self.voices() if v.key == key)

    def provider(self, voice: Voice) -> VoiceProvider:
        return self._providers[voice.provider]

    def available(self, voice: Voice) -> bool:
        return self.provider(voice).available()
