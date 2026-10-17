"""Shared recap vocabulary below both the agents and highlights layers: recap stages, turning points, moment actors.

RecapStage names the point in the match a recap or highlights reel covers, and MIN_TURNING_POINT_IMPORTANCE is
the key-moment importance a non-goal moment needs to count as a turning point in either.
moment_actor reads the main player named in a key moment's facts, for recap turning points and reel captions.
"""

from collections.abc import Mapping
from enum import StrEnum

MIN_TURNING_POINT_IMPORTANCE: float = 0.45
FACT_PLAYER_KEYS: tuple[str, ...] = ("scorer", "player", "goalkeeper", "passer")


class RecapStage(StrEnum):
    """Point in the match a recap covers."""

    HALF_TIME = "half_time"
    FULL_TIME = "full_time"


def moment_actor(facts: Mapping[str, object]) -> str | None:
    """Return the main player named in a moment's facts, if any."""
    return next((str(facts[k]) for k in FACT_PLAYER_KEYS if facts.get(k)), None)
