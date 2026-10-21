"""Function tools the analyst agent can call to look up live match statistics.

Every tool result is recorded in an EvidenceLedger so the grounding check accepts numbers the agent looked up.
Given a moment context, tools answer as of that moment, so a delayed job never cites later events or stats.
"""

import json
from dataclasses import dataclass, field
from typing import Annotated

from agent_framework import FunctionTool, tool

from insidegame.agents.context import MomentContext
from insidegame.analytics.analyzer import MatchAnalyzer

DEFAULT_RECENT_MOMENTS: int = 3
POSSESSION_DECIMALS: int = 1
MAX_RECENT_MOMENTS: int = 8


@dataclass
class EvidenceLedger:
    """Collects every payload returned by tools during one agent run."""

    entries: list[dict[str, object]] = field(default_factory=list)

    def record(self, tool_name: str, payload: object) -> str:
        """Store a tool payload and return it serialised for the model."""
        self.entries.append({"tool": tool_name, "payload": payload})
        return json.dumps(payload, ensure_ascii=False)


def build_analyst_tools(
    analyzer: MatchAnalyzer, ledger: EvidenceLedger, as_of: MomentContext | None = None
) -> list[FunctionTool]:
    """Create statistics lookup tools; with as_of, answers reflect the match at that moment.

    Defaults: as_of is None, meaning tools read the live match state.
    """

    def get_player_stats(player_name: Annotated[str, "Full name of the player, exactly as in the input."]) -> str:
        snapshot = next((stats for name, stats in (as_of.players.items() if as_of else ())
                         if name.lower() == player_name.lower()), None)
        if snapshot is not None:
            return ledger.record("get_player_stats", {"name": player_name, **snapshot})
        matches = [p.to_dict() for p in analyzer.stats.players.values() if p.name.lower() == player_name.lower()]
        return ledger.record("get_player_stats", matches[0] if matches else {"error": "unknown player"})

    def compare_teams() -> str:
        if as_of is not None:
            return ledger.record("compare_teams", as_of.teams)
        payload = {
            team.name: {"possession_pct": round(analyzer.stats.possession_share(team.team_id), POSSESSION_DECIMALS),
                        **analyzer.stats.teams[team.team_id].to_dict()}
            for team in (analyzer.metadata.home, analyzer.metadata.away)
        }
        return ledger.record("compare_teams", payload)

    def recent_moments(count: Annotated[int, "How many recent key moments to return."] = DEFAULT_RECENT_MOMENTS) -> str:
        bounded = max(1, min(count, MAX_RECENT_MOMENTS))
        cutoff = (as_of.moment.period, as_of.moment.match_second) if as_of else None
        visible = [m for m in analyzer.moments if cutoff is None or (m.period, m.match_second) <= cutoff]
        payload = [{"minute": m.minute_label, "kind": m.kind.value, "facts": m.facts} for m in visible[-bounded:]]
        return ledger.record("recent_moments", payload)

    return [
        tool(get_player_stats, name="get_player_stats", description="Live statistics for one player."),
        tool(compare_teams, name="compare_teams", description="Side-by-side team statistics and possession."),
        tool(recent_moments, name="recent_moments", description="The most recent key moments in the match."),
    ]
