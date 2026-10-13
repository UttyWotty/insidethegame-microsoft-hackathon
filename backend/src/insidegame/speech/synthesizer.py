"""Interface for turning a commentary line into spoken audio, implemented by adapters and test doubles.

Routes depend on this protocol rather than on Azure, keeping the API layer free of cloud specifics.
Implementations raise SpeechUnavailableError when they cannot produce audio for a line.
"""

from typing import Protocol


class SpeechSynthesizer(Protocol):
    """Produces MP3 audio for a line of text in a two-letter language."""

    async def synthesize(self, text: str, language: str) -> bytes:
        """Return MP3 audio for text spoken in language."""
        ...
