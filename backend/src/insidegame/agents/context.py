"""Builds compact, prompt-ready context for a key moment from the live match analyzer.

The context includes the moment's facts, the match state, the rhythm reading, and involved players' statistics.
Keeping context small and factual reduces latency and gives the grounding check a precise list of allowed numbers.
"""

from dataclasses import dataclass, field

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import KeyMoment
from insidegame.analytics.stats import ActionCounters
from insidegame.agents.personas import ViewerProfile
from insidegame.domain.match import MatchMetadata

PLAYER_CONTEXT_KEYS: tuple[str, ...] = (
    "passes_completed", "pass_accuracy", "shots", "goals", "xg", "carry_distance_m", "max_shot_speed_kmh",
    "tackles", "saves",
)
TEAM_CONTEXT_KEYS: tuple[str, ...] = ("shots", "shots_on_target", "xg", "pass_accuracy", "pressures")
RHYTHM_CONTEXT_KEYS: tuple[str, ...] = ("momentum", "chaos", "state")
POSSESSION_DECIMALS: int = 1
IMPORTANCE_DECIMALS: int = 2

ContextValue = str | int | float | bool | None


@dataclass(frozen=True)
class MomentContext:
    """Everything an agent may cite about one moment."""

    moment: KeyMoment
    minute: int
    home_name: str
    away_name: str
    score_home: int
    score_away: int
    team_name: str | None
    rhythm: dict[str, ContextValue] = field(default_factory=dict)
    teams: dict[str, dict[str, ContextValue]] = field(default_factory=dict)
    players: dict[str, dict[str, ContextValue]] = field(default_factory=dict)

    def to_prompt_dict(self) -> dict[str, object]:
        """Return the context as a JSON-friendly dict for prompts."""
        return {
            "minute": self.moment.minute_label,
            "moment": self.moment.kind.value,
            "importance": round(self.moment.importance, IMPORTANCE_DECIMALS),
            "team": self.team_name,
            "score": f"{self.home_name} {self.score_home}-{self.score_away} {self.away_name}",
            "facts": dict(self.moment.facts),
            "rhythm": self.rhythm,
            "teams": self.teams,
            "players": self.players,
        }


def _pick(counters: ActionCounters, keys: tuple[str, ...]) -> dict[str, ContextValue]:
    data = counters.to_dict()
    return {k: data[k] for k in keys if k in data}  # type: ignore[misc]


def build_moment_context(moment: KeyMoment, analyzer: MatchAnalyzer) -> MomentContext:
    """Assemble prompt context for a moment from the analyzer's current state."""
    metadata, stats = analyzer.metadata, analyzer.stats
    event = analyzer.last_event
    teams = {
        team.name: {
            "possession_pct": round(stats.possession_share(team.team_id), POSSESSION_DECIMALS),
            **_pick(stats.teams[team.team_id], TEAM_CONTEXT_KEYS),
        }
        for team in (metadata.home, metadata.away)
    }
    players = {stats.players[pid].name: _pick(stats.players[pid], PLAYER_CONTEXT_KEYS)
               for pid in moment.player_ids if pid in stats.players}
    reading = analyzer.last_reading.to_dict() if analyzer.last_reading else {}
    team_names = {metadata.home.team_id: metadata.home.name, metadata.away.team_id: metadata.away.name}
    return MomentContext(
        moment=moment, minute=moment.minute, home_name=metadata.home.name, away_name=metadata.away.name,
        score_home=event.score_home if event else 0, score_away=event.score_away if event else 0,
        team_name=team_names.get(moment.team_id) if moment.team_id else None,
        rhythm={k: reading[k] for k in RHYTHM_CONTEXT_KEYS if k in reading},  # type: ignore[misc]
        teams=teams, players=players,
    )


@dataclass(frozen=True)
class ViewerContext:
    """A viewer's profile resolved to display names for prompts and templates.

    Defaults: favourite_team_name and tracked_player_name are None when the viewer has not set them.
    """

    viewer: ViewerProfile
    favourite_team_name: str | None = None
    tracked_player_name: str | None = None


def build_viewer_context(viewer: ViewerProfile, metadata: MatchMetadata) -> ViewerContext:
    """Resolve a viewer's favourite club and player identifiers to names."""
    teams = {t.team_id: t for t in (metadata.home, metadata.away)}
    players = {p.player_id: p.name for t in teams.values() for p in t.players}
    team = teams.get(viewer.favourite_team_id) if viewer.favourite_team_id else None
    return ViewerContext(
        viewer=viewer,
        favourite_team_name=team.name if team else None,
        tracked_player_name=players.get(viewer.favourite_player_id) if viewer.favourite_player_id else None,
    )
