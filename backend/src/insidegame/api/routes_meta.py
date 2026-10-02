"""Metadata routes: health, diagnostics, clubs, personas, and languages.

Health only reads configuration and in-memory counters, never touching the model.
Diagnostics performs the heavier check of model endpoint reachability.
"""

import httpx
from fastapi import APIRouter, Request

from insidegame.adapters.model_client import ModelProvider, ModelRuntime
from insidegame.agents.personas import PERSONAS
from insidegame.api.models import HealthResponse
from insidegame.live.segments import SUGGESTED_LANGUAGES
from insidegame.simulation.roster import CLUB_PRESETS, build_fixture

DIAGNOSTICS_TIMEOUT_S: float = 3.0
ROSTER_SEED: int = 0
HTTP_OK: int = 200

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Liveness check based on configuration only."""
    runtime: ModelRuntime = request.app.state.runtime
    return HealthResponse(status="ok", model_provider=runtime.provider.value,
                          sessions=len(request.app.state.registry.sessions))


@router.get("/diagnostics")
async def diagnostics(request: Request) -> dict[str, object]:
    """Check that the configured model endpoint is reachable."""
    runtime: ModelRuntime = request.app.state.runtime
    if runtime.provider is ModelProvider.OFFLINE:
        return {"model_provider": runtime.provider.value, "model_reachable": None, "detail": "offline mode"}
    url = f"{str(runtime.client.client.base_url).rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=DIAGNOSTICS_TIMEOUT_S) as http:
            response = await http.get(url, headers={"Authorization": f"Bearer {runtime.client.client.api_key}"})
        return {"model_provider": runtime.provider.value, "model_reachable": response.status_code == HTTP_OK,
                "status_code": response.status_code}
    except httpx.HTTPError as exc:
        return {"model_provider": runtime.provider.value, "model_reachable": False, "detail": str(exc)}


@router.get("/clubs")
async def clubs() -> list[dict[str, object]]:
    """Fictional clubs with their styles and squads (squads shown for a reference seed)."""
    keys = list(CLUB_PRESETS)
    result = []
    for key, preset in CLUB_PRESETS.items():
        opponent = next(k for k in keys if k != key)
        team = build_fixture(key, opponent, ROSTER_SEED).home
        result.append({"key": key, "name": preset.name, "short_name": preset.short_name, "venue": preset.venue,
                       "style": preset.style.label, "team_id": team.team_id})
    return result


@router.get("/personas")
async def personas() -> list[dict[str, object]]:
    """The five personas and their characteristics."""
    return [{"key": p.key.value, "name": p.display_name, "audience": p.audience, "voice": p.voice,
             "max_words": p.max_words, "overlay_style": p.overlay_style.value, "perspective": p.perspective.value}
            for p in PERSONAS.values()]


@router.get("/languages")
async def languages() -> dict[str, str]:
    """Suggested output languages; any two-letter language code is accepted."""
    return SUGGESTED_LANGUAGES
