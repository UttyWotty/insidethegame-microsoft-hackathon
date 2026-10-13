"""Spoken commentary routes: whether server-side speech is available, and MP3 audio for a match's own lines.

Audio is only produced for commentary the live session generated, looked up by reference, never for arbitrary
text, and each client is rate-limited because neural speech is billed per character.
"""

import os
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from insidegame.api.clients import client_key
from insidegame.core.exceptions import RateLimitError, SpeechUnavailableError

SPEECH_MAX_PER_WINDOW: int = int(os.getenv("SPEECH_MAX_PER_MINUTE", "40"))
SPEECH_WINDOW_S: float = 60.0
AUDIO_MEDIA_TYPE: str = "audio/mpeg"
AUDIO_HEADERS: dict[str, str] = {"Cache-Control": "private, max-age=3600"}

router = APIRouter()


@router.get("/speech/status")
async def speech_status(request: Request) -> dict[str, bool]:
    """Whether neural speech is configured; reads configuration only, never calls the speech service."""
    return {"available": request.app.state.speech is not None}


@router.get("/matches/{session_id}/speech")
async def spoken_line(
    session_id: str, request: Request,
    ref: str = Query(description="Feed line id: a play-by-play line id, or moment-<moment_id> for commentary."),
    segment: str | None = Query(default=None, description="Viewer segment that received the moment commentary."),
) -> Response:
    """MP3 audio of one commentary line from this match, at most SPEECH_MAX_PER_MINUTE requests per client."""
    synthesizer = request.app.state.speech
    if synthesizer is None:
        raise SpeechUnavailableError("Spoken commentary is not configured on this deployment")
    client, now = client_key(request), time.monotonic()
    limiter = request.app.state.speech_limiter
    if not limiter.allow(client, now):
        raise RateLimitError(f"Too many speech requests; retry in {limiter.retry_after(client, now):.0f}s")
    text, language = request.app.state.registry.get(session_id).spoken_line(ref, segment)
    audio = await synthesizer.synthesize(text, language)
    return Response(audio, media_type=AUDIO_MEDIA_TYPE, headers=AUDIO_HEADERS)
