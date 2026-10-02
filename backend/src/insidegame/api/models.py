"""Request and response models for the HTTP API.

They define the public contract consumed by the frontend and by external integrators.
Defaults are explicit and documented on each field.
"""

from pydantic import BaseModel, Field

from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.live.pacing import DEFAULT_SPEED, MAX_SPEED, MIN_SPEED

DEFAULT_SEED: int = 7
DEFAULT_HOME: str = "kestrel_bay"
DEFAULT_AWAY: str = "ironvale"
MAX_QUESTION_CHARS: int = 300
MIN_QUESTION_CHARS: int = 3
DEFAULT_PERSONA: str = "casual"


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


class AskRequest(BaseModel):
    """A viewer's question to the Match Companion, with their personalization settings."""

    question: str = Field(min_length=MIN_QUESTION_CHARS, max_length=MAX_QUESTION_CHARS,
                          description=f"The question, {MIN_QUESTION_CHARS} to {MAX_QUESTION_CHARS} characters.")
    persona: str = Field(default=DEFAULT_PERSONA, description=f"Persona key; defaults to {DEFAULT_PERSONA}.")
    language: str = Field(default=DEFAULT_LANGUAGE, description=f"Answer language; defaults to {DEFAULT_LANGUAGE}.")
    team: str | None = Field(default=None, description="Favourite club team_id; required for superfan.")
    player: str | None = Field(default=None, description="Tracked player_id; required for player_tracker.")
