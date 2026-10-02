"""Producer console routes: audit what the agents produced, hold AI overlays, and release them to air.

When PRODUCER_KEY is set, every route requires it in the X-Producer-Key header, so a public deployment cannot be
steered by viewers. Without a key the console is open, which suits local development and demos.
"""

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from insidegame.live.registry import SessionRegistry

PRODUCER_KEY: str = os.getenv("PRODUCER_KEY", "")
HTTP_FORBIDDEN: int = 403

router = APIRouter(prefix="/matches/{session_id}/producer")


class HoldRequest(BaseModel):
    """Turn overlay holding on or off."""

    on: bool = Field(description="True to hold new AI overlays for approval.")


class ReleaseRequest(BaseModel):
    """Release held overlays.

    Defaults: moment_id is None, meaning release every held moment.
    """

    moment_id: str | None = Field(default=None, description="Moment to release; omit to release all.")


def _authorise(supplied: str | None) -> None:
    if PRODUCER_KEY and not hmac.compare_digest(supplied or "", PRODUCER_KEY):
        raise HTTPException(status_code=HTTP_FORBIDDEN, detail="producer key required")


def _registry(request: Request) -> SessionRegistry:
    return request.app.state.registry


@router.get("")
async def producer_state(session_id: str, request: Request,
                         x_producer_key: str | None = Header(default=None)) -> dict[str, object]:
    """Moment timeline, broadcast records with provenance, hold state, and pipeline health."""
    _authorise(x_producer_key)
    return _registry(request).get(session_id).producer_summary()


@router.post("/hold")
async def hold(session_id: str, body: HoldRequest, request: Request,
               x_producer_key: str | None = Header(default=None)) -> dict[str, object]:
    """Hold or stop holding new AI overlays."""
    _authorise(x_producer_key)
    _registry(request).get(session_id).set_hold(body.on)
    return {"hold": body.on}


@router.post("/release")
async def release(session_id: str, body: ReleaseRequest, request: Request,
                  x_producer_key: str | None = Header(default=None)) -> dict[str, object]:
    """Air held overlays for one moment or for all held moments."""
    _authorise(x_producer_key)
    return {"released_cues": _registry(request).get(session_id).release(body.moment_id)}
