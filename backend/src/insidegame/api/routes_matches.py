"""Match routes: create a live replay, list and inspect sessions, and stream a personalized feed.

The stream endpoint registers the caller's viewer segment and returns server-sent events.
Domain errors are translated to HTTP errors by the handlers registered in app.py.
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.agents.context import build_viewer_context
from insidegame.agents.question_context import build_question_context
from insidegame.agents.runner import OutputSource
from insidegame.agents.steps import answer_question
from insidegame.api.clients import client_key
from insidegame.api.models import AskRequest, CreateMatchRequest
from insidegame.api.sse import stream
from insidegame.live.registry import SessionRegistry
from insidegame.live.segments import fixture_segment_profile

SSE_MEDIA_TYPE: str = "text/event-stream"
SSE_HEADERS: dict[str, str] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
HTTP_CREATED: int = 201

router = APIRouter(prefix="/matches")


def _registry(request: Request) -> SessionRegistry:
    return request.app.state.registry


@router.post("", status_code=HTTP_CREATED)
async def create_match(body: CreateMatchRequest, request: Request) -> dict[str, object]:
    """Simulate a fixture and start its live replay, at most MATCH_CREATE_MAX_PER_MINUTE per client."""
    registry = _registry(request)
    registry.check_create_rate(client_key(request))
    session = registry.create(body.home, body.away, body.seed, body.speed)
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
    profile = fixture_segment_profile(session.result.metadata, persona, language, team, player)
    subscriber = session.subscribe(profile)
    return StreamingResponse(stream(session, subscriber), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)


@router.post("/{session_id}/ask")
async def ask(session_id: str, body: AskRequest, request: Request) -> dict[str, object]:
    """Answer a viewer's question about the live match in their persona's voice and language."""
    registry = _registry(request)
    session = registry.get(session_id)
    analyzer = session.service.analyzer
    profile = fixture_segment_profile(analyzer.metadata, body.persona, body.language, body.team, body.player)
    viewer = build_viewer_context(profile, analyzer.metadata)
    registry.check_ask_rate(session_id)
    outcome = await answer_question(registry.suite, body.question, build_question_context(analyzer), viewer,
                                    analyzer, registry.policy)
    return {**outcome.value.model_dump(mode="json"), "question": body.question,
            "language": DEFAULT_LANGUAGE if outcome.source is OutputSource.FALLBACK else body.language,
            "source": outcome.source.value, "latency_ms": outcome.latency_ms}
