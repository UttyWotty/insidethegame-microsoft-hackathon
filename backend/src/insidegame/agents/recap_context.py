"""Builds the evidence for automated half-time and full-time recaps from the match analyzer.

It selects the most important key moments, team statistics, and a standout player chosen by an impact score.
The same context feeds the editor agent's prompt, its grounding check, and the fallback recap template.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.stats import PlayerStats

MAX_RECAP_MOMENTS: int = 6
MIN_TURNING_POINT_IMPORTANCE: float = 0.45
POSSESSION_DECIMALS: int = 1
XG_DECIMALS: int = 2
IMPACT_GOAL: float = 3.0
IMPACT_XG: float = 2.0
IMPACT_COMPLETED_PASS: float = 0.02
IMPACT_DEFENSIVE_ACTION: float = 0.15
IMPACT_SAVE: float = 0.5
FACT_PLAYER_KEYS: tuple[str, ...] = ("scorer", "player", "goalkeeper", "passer")


class RecapStage(StrEnum):
    """Point in the match a recap covers."""

    HALF_TIME = "half_time"
    FULL_TIME = "full_time"


@dataclass(frozen=True)
class RecapContext:
    """Evidence for a recap."""

    stage: RecapStage
    home_name: str
    away_name: str
    score_home: int
    score_away: int
    teams: dict[str, dict[str, object]] = field(default_factory=dict)
    moments: list[dict[str, object]] = field(default_factory=list)
    standout: dict[str, object] = field(default_factory=dict)
    players: dict[str, dict[str, object]] = field(default_factory=dict)

    def to_prompt_dict(self) -> dict[str, object]:
        """Return the context as a JSON-friendly dict for prompts."""
        return {
            "stage": self.stage.value,
            "score": f"{self.home_name} {self.score_home}-{self.score_away} {self.away_name}",
            "teams": self.teams, "key_moments": self.moments, "standout_candidate": self.standout,
        }


def impact_score(player: PlayerStats) -> float:
    """Simple contribution score used to pick a standout player."""
    defensive = player.tackles + player.interceptions
    return (IMPACT_GOAL * player.goals + IMPACT_XG * player.xg + IMPACT_COMPLETED_PASS * player.passes_completed
            + IMPACT_DEFENSIVE_ACTION * defensive + IMPACT_SAVE * player.saves)


def moment_actor(facts: dict[str, object]) -> str | None:
    """Return the main player named in a moment's facts, if any."""
    return next((str(facts[k]) for k in FACT_PLAYER_KEYS if facts.get(k)), None)


def build_recap_context(analyzer: MatchAnalyzer, stage: RecapStage) -> RecapContext:
    """Assemble recap evidence from the analyzer's current state."""
    metadata, stats, event = analyzer.metadata, analyzer.stats, analyzer.last_event
    team_names = {metadata.home.team_id: metadata.home.name, metadata.away.team_id: metadata.away.name}
    turning = [m for m in analyzer.moments if m.importance >= MIN_TURNING_POINT_IMPORTANCE]
    top = sorted(turning, key=lambda m: m.importance, reverse=True)[:MAX_RECAP_MOMENTS]
    moments = [{"minute": m.minute_label, "kind": m.kind.value, "team": team_names.get(m.team_id or ""),
                "facts": dict(m.facts)} for m in sorted(top, key=lambda m: (m.period, m.match_second))]
    teams = {
        name: {"possession_pct": round(stats.possession_share(team_id), POSSESSION_DECIMALS),
               "shots": stats.teams[team_id].shots, "xg": round(stats.teams[team_id].xg, XG_DECIMALS),
               "pass_accuracy": round(stats.teams[team_id].pass_accuracy, XG_DECIMALS)}
        for team_id, name in team_names.items()
    }
    best = max(stats.players.values(), key=impact_score)
    standout = {"name": best.name, "team": team_names[best.team_id], "goals": best.goals,
                "xg": round(best.xg, XG_DECIMALS), "passes_completed": best.passes_completed}
    players = {p.name: {"team": team_names[p.team_id], "goals": p.goals, "shots": p.shots,
                        "xg": round(p.xg, XG_DECIMALS), "passes_completed": p.passes_completed,
                        "tackles": p.tackles} for p in stats.players.values()}
    return RecapContext(stage, metadata.home.name, metadata.away.name, event.score_home if event else 0,
                        event.score_away if event else 0, teams, moments, standout, players)
