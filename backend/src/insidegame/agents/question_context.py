"""Builds the live-match evidence a Match Companion answer may draw on.

It summarises the score, clock, team statistics, rhythm, the most influential players, and recent key moments;
every player's statistics are kept for direct lookups but left out of prompts, where tools provide them.
The same summary feeds the prompt, the grounding check, and the fallback answer.
"""

from dataclasses import dataclass, field

from insidegame.agents.recap_context import impact_score
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.core.clock import minute_label

TOP_PLAYERS: int = 5
RECENT_MOMENTS: int = 5
STAT_DECIMALS: int = 2
POSSESSION_DECIMALS: int = 1
KICK_OFF_LABEL: str = "pre-match"


@dataclass(frozen=True)
class QuestionContext:
    """Snapshot of the live match for answering questions."""

    home_name: str
    away_name: str
    score_home: int
    score_away: int
    clock: str
    teams: dict[str, dict[str, object]] = field(default_factory=dict)
    rhythm: dict[str, object] = field(default_factory=dict)
    top_players: list[dict[str, object]] = field(default_factory=list)
    recent_moments: list[dict[str, object]] = field(default_factory=list)
    players: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def scoreline(self) -> str:
        """Human-readable score."""
        return f"{self.home_name} {self.score_home}-{self.score_away} {self.away_name}"

    def to_prompt_dict(self) -> dict[str, object]:
        """Return the context as a JSON-friendly dict for prompts."""
        return {"score": self.scoreline, "clock": self.clock, "teams": self.teams, "rhythm": self.rhythm,
                "top_players": self.top_players, "recent_moments": self.recent_moments}


def build_question_context(analyzer: MatchAnalyzer) -> QuestionContext:
    """Summarise the analyzer's current state for the Match Companion."""
    metadata, stats, event = analyzer.metadata, analyzer.stats, analyzer.last_event
    names = {metadata.home.team_id: metadata.home.name, metadata.away.team_id: metadata.away.name}
    teams = {
        name: {"possession_pct": round(stats.possession_share(team_id), POSSESSION_DECIMALS),
               "shots": stats.teams[team_id].shots, "shots_on_target": stats.teams[team_id].shots_on_target,
               "xg": round(stats.teams[team_id].xg, STAT_DECIMALS),
               "pass_accuracy": round(stats.teams[team_id].pass_accuracy, STAT_DECIMALS)}
        for team_id, name in names.items()
    }
    best = sorted(stats.players.values(), key=impact_score, reverse=True)[:TOP_PLAYERS]
    top_players = [{"name": p.name, "team": names[p.team_id], "goals": p.goals, "xg": round(p.xg, STAT_DECIMALS),
                    "passes_completed": p.passes_completed, "tackles": p.tackles} for p in best]
    recent = [{"minute": m.minute_label, "kind": m.kind.value, "facts": dict(m.facts)}
              for m in analyzer.moments[-RECENT_MOMENTS:]]
    players = {p.name: {"team": names[p.team_id], "goals": p.goals, "shots": p.shots, "xg": round(p.xg, STAT_DECIMALS),
                        "passes_completed": p.passes_completed, "tackles": p.tackles,
                        "carry_distance_m": round(p.carry_distance_m, STAT_DECIMALS)} for p in stats.players.values()}
    reading = analyzer.last_reading.to_dict() if analyzer.last_reading else {}
    return QuestionContext(
        home_name=metadata.home.name, away_name=metadata.away.name,
        score_home=event.score_home if event else 0, score_away=event.score_away if event else 0,
        clock=minute_label(event.match_second, event.period) if event else KICK_OFF_LABEL,
        teams=teams, rhythm={k: reading[k] for k in ("momentum", "chaos", "state") if k in reading},
        top_players=top_players, recent_moments=recent, players=players,
    )
