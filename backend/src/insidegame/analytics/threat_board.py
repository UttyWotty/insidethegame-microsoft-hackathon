"""Pure ranking of players by the expected threat (xT) their completed passes and carries added.

Only players who added positive xT appear, ordered by xT added, then line-breaking passes, then name.
The board feeds the snapshot, the MCP server, and the Match Companion's question context.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from insidegame.analytics.stats import PlayerStats
from insidegame.analytics.threat import XT_DECIMALS


@dataclass(frozen=True)
class ThreatLeader:
    """One row of the danger leaderboard."""

    player_id: str
    name: str
    team_id: str
    xt_added: float
    line_breaking_passes: int
    opponents_bypassed: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation with xT rounded to XT_DECIMALS."""
        return {"player_id": self.player_id, "name": self.name, "team_id": self.team_id,
                "xt_added": round(self.xt_added, XT_DECIMALS), "line_breaking_passes": self.line_breaking_passes,
                "opponents_bypassed": self.opponents_bypassed}


def threat_leaders(players: Iterable[PlayerStats], limit: int) -> list[ThreatLeader]:
    """Return at most limit players with positive xT added, most dangerous first."""
    ranked = sorted((p for p in players if p.xt_added > 0),
                    key=lambda p: (-p.xt_added, -p.line_breaking_passes, p.name))
    return [ThreatLeader(p.player_id, p.name, p.team_id, p.xt_added, p.line_breaking_passes, p.opponents_bypassed)
            for p in ranked[:limit]]
