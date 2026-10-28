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

    def load(self) -> None:
        """Gets ready to synthesize (loads a model, say); may take long, so the core calls it once, on its synthesis
        thread, before anything is synthesized. An error means the provider's Voices cannot be used."""
        ...

    def available(self) -> bool:
        """Whether the provider can synthesize right now (model loaded, connection up)."""
        ...

    def synthesize(self, text: str, voice: str, speed: float) -> Audio:
        """Synthesizes one piece of text with one of this provider's Voices at a Speed."""
        ...

    def sample(self, voice: str) -> Audio | None:
        """A ready-made Voice sample of 5 to 7 seconds, played at once even before the provider is available;
        None for a Voice it does not have."""
        ...


class VoiceRegistry:
    def __init__(self, providers: list[VoiceProvider]):
        self._providers = {p.id: p for p in providers}

    def providers(self) -> list[VoiceProvider]:
        return list(self._providers.values())

    def voices(self) -> list[Voice]:
        return [v for p in self._providers.values() for v in p.voices()]

    def voice(self, key: str) -> Voice | None:
        return next((v for v in self.voices() if v.key == key), None)

    def provider(self, voice: Voice) -> VoiceProvider:
        return self._providers[voice.provider]

    def available(self, voice: Voice) -> bool:
        return self.provider(voice).available()
