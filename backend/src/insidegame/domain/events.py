"""The MatchEvent model, the machine-readable contract for every pipeline stage.

Coordinates are relative to the acting team, which attacks toward x = 105.
Optional detail fields are populated only for event types where they apply and default to None.
"""

from dataclasses import dataclass

from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Outcome, ShotResult

SPEED_DECIMALS: int = 1
TIME_DECIMALS: int = 2


@dataclass(frozen=True)
class MatchEvent:
    """A single on-ball or match-flow event.

    Defaults: all detail fields default to None (not applicable) and under_pressure to False.
    """

    event_id: str
    match_id: str
    sequence: int
    period: int
    match_second: float
    event_type: EventType
    team_id: str | None
    player_id: str | None
    possession_id: int
    start: Point | None
    score_home: int
    score_away: int
    end: Point | None = None
    outcome: Outcome | None = None
    receiver_id: str | None = None
    opponent_id: str | None = None
    under_pressure: bool = False
    length_m: float | None = None
    ball_speed_kmh: float | None = None
    shot_result: ShotResult | None = None

    @property
    def minute(self) -> int:
        """Return the broadcast-style match minute, starting at 1."""
        return int(self.match_second // SECONDS_PER_MINUTE) + 1

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation with enums as strings."""
        return {
            "event_id": self.event_id,
            "match_id": self.match_id,
            "sequence": self.sequence,
            "period": self.period,
            "match_second": round(self.match_second, TIME_DECIMALS),
            "minute": self.minute,
            "event_type": self.event_type.value,
            "team_id": self.team_id,
            "player_id": self.player_id,
            "possession_id": self.possession_id,
            "start": self.start.to_dict() if self.start else None,
            "end": self.end.to_dict() if self.end else None,
            "outcome": self.outcome.value if self.outcome else None,
            "receiver_id": self.receiver_id,
            "opponent_id": self.opponent_id,
            "under_pressure": self.under_pressure,
            "length_m": round(self.length_m, TIME_DECIMALS) if self.length_m is not None else None,
            "ball_speed_kmh": round(self.ball_speed_kmh, SPEED_DECIMALS) if self.ball_speed_kmh is not None else None,
            "shot_result": self.shot_result.value if self.shot_result else None,
            "score": {"home": self.score_home, "away": self.score_away},
        }
