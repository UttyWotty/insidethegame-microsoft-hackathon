"""Function tools the analyst agent can call to look up live match statistics.

Every tool result is recorded in an EvidenceLedger so the grounding check accepts numbers the agent looked up.
Tools read in-memory analyzer state only and never perform I/O.
"""

import json
from dataclasses import dataclass, field
from typing import Annotated

from agent_framework import FunctionTool, tool

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


def build_analyst_tools(analyzer: MatchAnalyzer, ledger: EvidenceLedger) -> list[FunctionTool]:
    """Create statistics lookup tools bound to one match analyzer and evidence ledger."""

    def get_player_stats(player_name: Annotated[str, "Full name of the player, exactly as in the input."]) -> str:
        matches = [p.to_dict() for p in analyzer.stats.players.values() if p.name.lower() == player_name.lower()]
        return ledger.record("get_player_stats", matches[0] if matches else {"error": "unknown player"})

    def compare_teams() -> str:
        payload = {
            team.name: {"possession_pct": round(analyzer.stats.possession_share(team.team_id), POSSESSION_DECIMALS),
                        **analyzer.stats.teams[team.team_id].to_dict()}
            for team in (analyzer.metadata.home, analyzer.metadata.away)
        }
        return ledger.record("compare_teams", payload)

    def recent_moments(count: Annotated[int, "How many recent key moments to return."] = DEFAULT_RECENT_MOMENTS) -> str:
        bounded = max(1, min(count, MAX_RECENT_MOMENTS))
        payload = [{"minute": m.minute, "kind": m.kind.value, "facts": m.facts} for m in analyzer.moments[-bounded:]]
        return ledger.record("recent_moments", payload)

    return [
        tool(get_player_stats, name="get_player_stats", description="Live statistics for one player."),
        tool(compare_teams, name="compare_teams", description="Side-by-side team statistics and possession."),
        tool(recent_moments, name="recent_moments", description="The most recent key moments in the match."),
    ]
