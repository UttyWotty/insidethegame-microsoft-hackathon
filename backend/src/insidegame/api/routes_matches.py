"""Match routes: create a live replay, list and inspect sessions, and stream a personalized feed.

The stream endpoint registers the caller's viewer segment and returns server-sent events.
Domain errors are translated to HTTP errors by the handlers registered in app.py.
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.api.models import CreateMatchRequest
from insidegame.api.sse import stream
from insidegame.live.registry import SessionRegistry
from insidegame.live.segments import build_segment_profile

SSE_MEDIA_TYPE: str = "text/event-stream"
SSE_HEADERS: dict[str, str] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
HTTP_CREATED: int = 201

router = APIRouter(prefix="/matches")


def _registry(request: Request) -> SessionRegistry:
    return request.app.state.registry


@router.post("", status_code=HTTP_CREATED)
async def create_match(body: CreateMatchRequest, request: Request) -> dict[str, object]:
    """Simulate a fixture and start its live replay."""
    session = _registry(request).create(body.home, body.away, body.seed, body.speed)
    return session.describe()


@router.get("")
async def list_matches(request: Request) -> list[dict[str, object]]:
    """All known sessions."""
    return [s.describe() for s in _registry(request).sessions.values()]


@router.get("/{session_id}")
async def get_match(session_id: str, request: Request) -> dict[str, object]:
    """Session summary, current interpreted state, and recaps so far."""
    session = _registry(request).get(session_id)
    return {**session.describe(), "snapshot": session.snapshot(), "recaps": session.recaps}


@router.get("/{session_id}/stream")
async def stream_match(
    session_id: str, request: Request,
    persona: str = Query(description="Persona key, for example analyst or casual."),
    language: str = Query(default=DEFAULT_LANGUAGE, description=f"Language code; defaults to {DEFAULT_LANGUAGE}."),
    team: str | None = Query(default=None, description="Favourite club team_id; required for superfan."),
    player: str | None = Query(default=None, description="Tracked player_id; required for player_tracker."),
) -> StreamingResponse:
    """Server-sent events: match, event, snapshot, cue, recap, and end messages for one viewer segment."""
    session = _registry(request).get(session_id)
    subscriber = session.subscribe(build_segment_profile(persona, language, team, player))
    return StreamingResponse(stream(session, subscriber), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)
