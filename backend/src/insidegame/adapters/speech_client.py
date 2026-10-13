"""Azure AI Speech adapter: neural text to speech over REST with keyless Microsoft Entra authentication.

It posts SSML to the AI Services resource's custom-domain endpoint with a managed identity token and returns MP3.
Recent lines are cached because every viewer of a segment hears the same commentary; failures become
SpeechUnavailableError so the browser can fall back to on-device speech.
"""

import asyncio
import logging
import os
from collections import OrderedDict
from collections.abc import Awaitable, Callable

import httpx
from azure.identity import DefaultAzureCredential

from insidegame.core.exceptions import SpeechUnavailableError
from insidegame.speech.ssml import build_ssml, voice_for

SPEECH_ENDPOINT: str = os.getenv("SPEECH_ENDPOINT", "")
AZURE_CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
SPEECH_TIMEOUT_S: float = float(os.getenv("SPEECH_TIMEOUT_S", "10"))
TOKEN_SCOPE: str = "https://cognitiveservices.azure.com/.default"
SYNTHESIS_PATH: str = "tts/cognitiveservices/v1"
OUTPUT_FORMAT: str = "audio-24khz-48kbitrate-mono-mp3"
SSML_MEDIA_TYPE: str = "application/ssml+xml"
USER_AGENT: str = "inside-the-game"
DEFAULT_CACHE_SIZE: int = 256

TokenProvider = Callable[[], Awaitable[str]]

logger = logging.getLogger(__name__)


class AzureSpeechClient:
    """Synthesizes commentary with Azure AI Speech, caching the most recent lines."""

    def __init__(self, endpoint: str, token: TokenProvider, http: httpx.AsyncClient | None = None,
                 cache_size: int = DEFAULT_CACHE_SIZE) -> None:
        """Create a client for an AI Services endpoint such as https://name.cognitiveservices.azure.com/.

        Defaults: http is a new httpx.AsyncClient with SPEECH_TIMEOUT_S; cache_size is DEFAULT_CACHE_SIZE lines.
        """
        self.url = endpoint.rstrip("/") + "/" + SYNTHESIS_PATH
        self.token = token
        self.http = http or httpx.AsyncClient(timeout=SPEECH_TIMEOUT_S)
        self.cache_size = cache_size
        self.cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()

    async def synthesize(self, text: str, language: str) -> bytes:
        """Return MP3 audio for text in language, from the cache when this line was spoken recently."""
        voice = voice_for(language)
        if voice is None:
            raise SpeechUnavailableError(f"No neural voice is configured for language {language!r}")
        key = (voice, text)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        audio = await self._request(build_ssml(text, voice))
        self.cache[key] = audio
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return audio

    async def _request(self, ssml: str) -> bytes:
        try:
            headers = {"Authorization": f"Bearer {await self.token()}", "Content-Type": SSML_MEDIA_TYPE,
                       "X-Microsoft-OutputFormat": OUTPUT_FORMAT, "User-Agent": USER_AGENT}
            response = await self.http.post(self.url, content=ssml.encode("utf-8"), headers=headers)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - token or HTTP failure; the browser falls back to local speech
            logger.warning("Speech synthesis failed: %s", exc)
            raise SpeechUnavailableError("Speech synthesis failed") from exc
        return response.content


def _managed_identity_token() -> TokenProvider:
    credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)

    async def token() -> str:
        access = await asyncio.to_thread(credential.get_token, TOKEN_SCOPE)
        return access.token

    return token


def build_speech_client() -> AzureSpeechClient | None:
    """The Azure speech client when SPEECH_ENDPOINT is set, otherwise None (browser speech only)."""
    return AzureSpeechClient(SPEECH_ENDPOINT, _managed_identity_token()) if SPEECH_ENDPOINT else None
