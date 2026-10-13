"""Interface for turning a commentary line into spoken audio, implemented by adapters and test doubles.

Routes depend on this protocol rather than on Azure, keeping the API layer free of cloud specifics.
Implementations raise SpeechUnavailableError when they cannot produce audio for a line.
"""

from typing import Protocol

from insidegame.domain.enums import Intensity


class SpeechSynthesizer(Protocol):
    """Produces MP3 audio for a line of text in a two-letter language."""

    async def synthesize(self, text: str, language: str, intensity: Intensity, pace: float) -> bytes:
        """Return MP3 audio for text in language, delivered for the intensity at the given base pace."""
        ...
