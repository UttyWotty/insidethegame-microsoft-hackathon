"""Running per-player and per-team statistics built incrementally from the event stream.

StatsAccumulator applies one event at a time, using precomputed xG and pass quality values.
It also attributes elapsed time to the team in possession to derive possession share, and credits the expected
threat (xT) and line breaks of completed passes and carries to the acting player and team.
"""

from dataclasses import asdict, dataclass, field

from insidegame.analytics.pass_quality import PassQuality
from insidegame.analytics.threat import XT_DECIMALS, ThreatAction
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

ON_TARGET_RESULTS: frozenset[ShotResult] = frozenset({ShotResult.GOAL, ShotResult.SAVED})
RATIO_DECIMALS: int = 3
STAT_DECIMALS: int = 2
PERCENT: float = 100.0


@dataclass
class ActionCounters:
    """Counters shared by player and team statistics."""

    passes_attempted: int = 0
    passes_completed: int = 0
    pass_difficulty_total: float = 0.0
    progressive_passes: int = 0
    final_third_entries: int = 0
    shots: int = 0
    shots_on_target: int = 0
    goals: int = 0
    xg: float = 0.0
    max_shot_speed_kmh: float = 0.0
    carries: int = 0
    carry_distance_m: float = 0.0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0
    fouls: int = 0
    saves: int = 0
    xt_added: float = 0.0
    line_breaking_passes: int = 0
    opponents_bypassed: int = 0

    @property
    def pass_accuracy(self) -> float:
        """Share of attempted passes that were completed, 0 when none were attempted."""
        return self.passes_completed / self.passes_attempted if self.passes_attempted else 0.0

    @property
    def avg_pass_difficulty(self) -> float:
        """Mean difficulty rating of attempted passes, 0 when none were attempted."""
        return self.pass_difficulty_total / self.passes_attempted if self.passes_attempted else 0.0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation including derived ratios."""
        data = {k: round(v, STAT_DECIMALS) if isinstance(v, float) else v for k, v in asdict(self).items()}
        data.pop("pass_difficulty_total")
        data["pass_accuracy"] = round(self.pass_accuracy, RATIO_DECIMALS)
        data["avg_pass_difficulty"] = round(self.avg_pass_difficulty, STAT_DECIMALS)
        data["xt_added"] = round(self.xt_added, XT_DECIMALS)
        return data


@dataclass
class PlayerStats(ActionCounters):
    """Running statistics for one player."""

    player_id: str = ""
    team_id: str = ""
    name: str = ""


@dataclass
class TeamStats(ActionCounters):
    """Running statistics for one team, including time in possession."""

    team_id: str = ""
    possession_seconds: float = 0.0


def _apply_counters(c: ActionCounters, event: MatchEvent, xg: float | None, quality: PassQuality | None) -> None:
    kind = event.event_type
    if kind is EventType.PASS and quality is not None:
        c.passes_attempted += 1
        c.pass_difficulty_total += quality.difficulty
        if event.outcome is Outcome.SUCCESS:
            c.passes_completed += 1
            c.progressive_passes += quality.progressive
            c.final_third_entries += quality.final_third_entry
    elif kind is EventType.SHOT and xg is not None:
        c.shots += 1
        c.xg += xg
        c.shots_on_target += event.shot_result in ON_TARGET_RESULTS
        c.max_shot_speed_kmh = max(c.max_shot_speed_kmh, event.ball_speed_kmh or 0.0)
    elif kind is EventType.GOAL:
        c.goals += 1
    elif kind is EventType.CARRY:
        c.carries += 1
        c.carry_distance_m += event.length_m or 0.0
    elif kind is EventType.TACKLE:
        c.tackles += 1
    elif kind is EventType.INTERCEPTION:
        c.interceptions += 1
    elif kind is EventType.PRESSURE:
        c.pressures += 1
    elif kind is EventType.FOUL:
        c.fouls += 1
    elif kind is EventType.SAVE:
        c.saves += 1


def _apply_threat(c: ActionCounters, threat: ThreatAction) -> None:
    c.xt_added += threat.xt_added
    if threat.line_break is not None:
        c.line_breaking_passes += threat.line_break.breaks_line
        c.opponents_bypassed += threat.line_break.opponents_bypassed


@dataclass
class StatsAccumulator:
    """Incrementally maintains player and team statistics for one match."""

    metadata: MatchMetadata
    players: dict[str, PlayerStats] = field(default_factory=dict)
    teams: dict[str, TeamStats] = field(default_factory=dict)
    possessing_team_id: str | None = None
    last_second: float | None = None

    def __post_init__(self) -> None:
        for team in (self.metadata.home, self.metadata.away):
            self.teams[team.team_id] = TeamStats(team_id=team.team_id)
            for p in team.players:
                self.players[p.player_id] = PlayerStats(player_id=p.player_id, team_id=team.team_id, name=p.name)

    def apply(self, event: MatchEvent, xg: float | None, quality: PassQuality | None,
              threat: ThreatAction | None = None) -> None:
        """Update statistics with one event; threat (default None) is the xT credit of a completed pass or carry."""
        self._track_possession(event)
        if event.team_id is None:
            return
        _apply_counters(self.teams[event.team_id], event, xg, quality)
        if event.player_id is not None:
            _apply_counters(self.players[event.player_id], event, xg, quality)
        if threat is not None:
            _apply_threat(self.teams[threat.team_id], threat)
            _apply_threat(self.players[threat.player_id], threat)

    def _track_possession(self, event: MatchEvent) -> None:
        if event.event_type is EventType.PERIOD_START:
            self.possessing_team_id, self.last_second = None, event.match_second
            return
        if self.possessing_team_id is not None and self.last_second is not None:
            self.teams[self.possessing_team_id].possession_seconds += event.match_second - self.last_second
        self.last_second = event.match_second
        if event.event_type in (EventType.KICK_OFF, EventType.POSSESSION_CHANGE):
            self.possessing_team_id = event.team_id

    def possession_share(self, team_id: str) -> float:
        """Percentage of attributed time the team has had the ball."""
        total = sum(t.possession_seconds for t in self.teams.values())
        return PERCENT * self.teams[team_id].possession_seconds / total if total else PERCENT / len(self.teams)
