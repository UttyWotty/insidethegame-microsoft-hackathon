"""Request and response models for the HTTP API.

They define the public contract consumed by the frontend and by external integrators.
Defaults are explicit and documented on each field.
"""

from pydantic import BaseModel, Field

from insidegame.live.pacing import DEFAULT_SPEED, MAX_SPEED, MIN_SPEED

DEFAULT_SEED: int = 7
DEFAULT_HOME: str = "kestrel_bay"
DEFAULT_AWAY: str = "ironvale"


class CreateMatchRequest(BaseModel):
    """Start a new live replay of a simulated fixture."""

    home: str = Field(default=DEFAULT_HOME, description=f"Home club preset key; defaults to {DEFAULT_HOME}.")
    away: str = Field(default=DEFAULT_AWAY, description=f"Away club preset key; defaults to {DEFAULT_AWAY}.")
    seed: int = Field(default=DEFAULT_SEED, description=f"Simulation seed; defaults to {DEFAULT_SEED}.")
    speed: float = Field(default=DEFAULT_SPEED, ge=MIN_SPEED, le=MAX_SPEED,
                         description=f"Match seconds per real second; defaults to {DEFAULT_SPEED}.")


class HealthResponse(BaseModel):
    """Lightweight liveness information read from configuration only."""

    status: str
    model_provider: str
    sessions: int
