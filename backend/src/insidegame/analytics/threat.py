"""Pure per-event threat assessment: the expected threat (xT) a completed pass or carry added, and any line break.

xT added is the grid value where the ball ended minus where it started, credited to the acting player and team.
Line breaks are assessed only for passes, and only when the opponents' positions before the pass are known.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from insidegame.analytics.line_breaks import LineBreak, assess_line_break, opponent_lines
from insidegame.analytics.xt import xt_value
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

XT_DECIMALS: int = 3
THREAT_ACTIONS: frozenset[EventType] = frozenset({EventType.PASS, EventType.CARRY})


@dataclass(frozen=True)
class ThreatAction:
    """The threat one completed pass or carry created.

    Defaults: none; receiver_id is None for carries and line_break is None for carries or without positions.
    """

    event_id: str
    team_id: str
    player_id: str
    receiver_id: str | None
    action: EventType
    xt_start: float
    xt_end: float
    line_break: LineBreak | None

    @property
    def xt_added(self) -> float:
        """xT at the end minus xT at the start; negative when the ball moved somewhere less dangerous."""
        return self.xt_end - self.xt_start

    @property
    def breaks_line(self) -> bool:
        """Whether a line break was assessed and broke at least one line."""
        return self.line_break is not None and self.line_break.breaks_line

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation with xT values rounded to XT_DECIMALS."""
        return {
            "event_id": self.event_id, "team_id": self.team_id, "player_id": self.player_id,
            "action": self.action.value, "xt_start": round(self.xt_start, XT_DECIMALS),
            "xt_end": round(self.xt_end, XT_DECIMALS), "xt_added": round(self.xt_added, XT_DECIMALS),
            "opponents_bypassed": self.line_break.opponents_bypassed if self.line_break else None,
            "lines_broken": [line.value for line in self.line_break.lines_broken] if self.line_break else [],
            "breaks_line": self.breaks_line,
        }


def _line_break(event: MatchEvent, team_id: str, start: Point, end: Point, metadata: MatchMetadata,
                positions_before: Mapping[str, Point] | None) -> LineBreak | None:
    if event.event_type is not EventType.PASS or not positions_before:
        return None
    return assess_line_break(start, end, opponent_lines(team_id, metadata, positions_before))


def assess_threat(event: MatchEvent, metadata: MatchMetadata,
                  positions_before: Mapping[str, Point] | None) -> ThreatAction | None:
    """Assess a completed pass or carry; None for any other event or when team, player, start, or end is missing.

    positions_before holds absolute home-frame positions before the event; None or empty means no line break.
    """
    team_id, player_id, start, end = event.team_id, event.player_id, event.start, event.end
    if (event.event_type not in THREAT_ACTIONS or event.outcome is not Outcome.SUCCESS or team_id is None
            or player_id is None or start is None or end is None):
        return None
    return ThreatAction(
        event_id=event.event_id, team_id=team_id, player_id=player_id, receiver_id=event.receiver_id,
        action=event.event_type, xt_start=xt_value(start), xt_end=xt_value(end),
        line_break=_line_break(event, team_id, start, end, metadata, positions_before),
    )
