"""Key moment model: the structured evidence handed to explanation and narration agents.

A KeyMoment names what happened, how important it is, who was involved, and the facts that justify it.
Facts are JSON scalars so they can be rendered as overlays or placed directly into agent prompts.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.core.clock import minute_label
from insidegame.core.constants import SECONDS_PER_MINUTE

IMPORTANCE_DECIMALS: int = 3

FactValue = str | int | float | bool | None


class MomentKind(StrEnum):
    """Category of a detected key moment."""

    GOAL = "goal"
    BIG_CHANCE_MISSED = "big_chance_missed"
    GREAT_SAVE = "great_save"
    SPEED_THRESHOLD = "speed_threshold"
    DISTANCE_THRESHOLD = "distance_threshold"
    DIFFICULT_PASS = "difficult_pass"
    MOMENTUM_SWING = "momentum_swing"
    CHAOS_SPELL = "chaos_spell"
    MILESTONE = "milestone"


@dataclass(frozen=True)
class KeyMoment:
    """A moment worth surfacing, with machine-readable supporting evidence."""

    moment_id: str
    kind: MomentKind
    period: int
    match_second: float
    importance: float
    team_id: str | None
    player_ids: tuple[str, ...] = field(default_factory=tuple)
    event_ids: tuple[str, ...] = field(default_factory=tuple)
    facts: dict[str, FactValue] = field(default_factory=dict)

    @property
    def minute(self) -> int:
        """Broadcast-style match minute, starting at 1."""
        return int(self.match_second // SECONDS_PER_MINUTE) + 1

    @property
    def minute_label(self) -> str:
        """Broadcast minute label including added time, for example 45+3'."""
        return minute_label(self.match_second, self.period)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "moment_id": self.moment_id,
            "kind": self.kind.value,
            "period": self.period,
            "match_second": self.match_second,
            "minute": self.minute,
            "minute_label": self.minute_label,
            "importance": round(self.importance, IMPORTANCE_DECIMALS),
            "team_id": self.team_id,
            "player_ids": list(self.player_ids),
            "event_ids": list(self.event_ids),
            "facts": dict(self.facts),
        }
