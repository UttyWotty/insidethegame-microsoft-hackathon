"""Streaming facade for pipeline stage two, turning each raw event into interpreted output.

MatchAnalyzer.ingest computes xG, pass quality, the expected threat (xT) of completed passes and carries (with line
breaks when tracking positions are supplied), a broadcast shot card, and live win probability, updates statistics and
rhythm, tracks each team's out-of-possession shape (and its line-height shifts) from those positions, and detects
key moments.
snapshot returns the full machine-readable match state for overlays, agents, and APIs.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from insidegame.analytics.detectors import MomentDetector
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.analytics.pass_quality import PassQuality, assess_pass
from insidegame.analytics.rhythm import RhythmReading, RhythmTracker
from insidegame.analytics.shape_tracker import ShapeTracker
from insidegame.analytics.shot_card import ShotCard, shot_card
from insidegame.analytics.threat import ThreatAction, assess_threat
from insidegame.analytics.threat_board import threat_leaders
from insidegame.analytics.win_probability import WinProbability, win_probability
from insidegame.analytics.stats import StatsAccumulator
from insidegame.analytics.xg import expected_goals
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

POSSESSION_DECIMALS: int = 1
FINAL_PERIOD: int = 2
THREAT_LEADERS_IN_SNAPSHOT: int = 5


@dataclass(frozen=True)
class AnalysisUpdate:
    """Everything stage two derived from a single event.

    Defaults: shot is None except on shot events; win is None only when built without it; threat is None except on
    completed passes and carries.
    """

    event: MatchEvent
    xg: float | None
    pass_quality: PassQuality | None
    rhythm: RhythmReading
    moments: tuple[KeyMoment, ...]
    shot: ShotCard | None = None
    win: WinProbability | None = None
    threat: ThreatAction | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "event": self.event.to_dict(),
            "xg": self.xg,
            "pass_quality": self.pass_quality.to_dict() if self.pass_quality else None,
            "rhythm": self.rhythm.to_dict(),
            "moments": [m.to_dict() for m in self.moments],
            "shot": self.shot.to_dict() if self.shot else None,
            "win": self.win.to_dict() if self.win else None,
            "threat": self.threat.to_dict() if self.threat else None,
        }


@dataclass
class MatchAnalyzer:
    """Stateful, I/O-free interpreter for one match's event stream."""

    metadata: MatchMetadata
    stats: StatsAccumulator = field(init=False)
    rhythm: RhythmTracker = field(default_factory=RhythmTracker)
    detector: MomentDetector = field(init=False)
    shape: ShapeTracker = field(init=False)
    moments: list[KeyMoment] = field(default_factory=list)
    last_event: MatchEvent | None = None
    last_reading: RhythmReading | None = None

    def __post_init__(self) -> None:
        self.stats = StatsAccumulator(self.metadata)
        self.detector = MomentDetector(self.metadata)
        self.shape = ShapeTracker(self.metadata)

    def ingest(self, event: MatchEvent, positions_before: Mapping[str, Point] | None = None) -> AnalysisUpdate:
        """Interpret one event and return the derived update.

        positions_before (default None, no line breaks and no shape) holds absolute home-frame player positions
        before this event, as tracked live, so passes can be assessed for opponents bypassed and lines broken and
        each team's shape can be sampled.
        """
        xg = expected_goals(event.start, event.under_pressure) if (
            event.event_type is EventType.SHOT and event.start) else None
        quality = assess_pass(event.start, event.end, event.under_pressure) if (
            event.event_type is EventType.PASS and event.start and event.end) else None
        threat = assess_threat(event, self.metadata, positions_before)
        side = self.metadata.side_of(event.team_id) if event.team_id else None
        self.stats.apply(event, xg, quality, threat)
        reading = self.rhythm.update(event, side, xg, quality)
        shifts = self.shape.observe(event, positions_before)
        new_moments = tuple(self.detector.detect(event, xg, quality, reading, threat=threat, shifts=shifts))
        self.moments.extend(new_moments)
        self.last_event, self.last_reading = event, reading
        card = shot_card(event, xg) if xg is not None else None
        return AnalysisUpdate(event, xg, quality, reading, new_moments, card, self._win(event), threat)

    def _win(self, event: MatchEvent) -> WinProbability:
        """Live win probability after this event."""
        home, away = self.metadata.home.team_id, self.metadata.away.team_id
        finished = event.event_type is EventType.PERIOD_END and event.period == FINAL_PERIOD
        return win_probability(event.score_home, event.score_away, self.stats.teams[home].xg,
                               self.stats.teams[away].xg, event.match_second, finished)

    def _team_block(self, side: Side) -> dict[str, object]:
        team = self.metadata.team(side)
        return {
            "team_id": team.team_id,
            "name": team.name,
            "short_name": team.short_name,
            "possession_pct": round(self.stats.possession_share(team.team_id), POSSESSION_DECIMALS),
            "stats": self.stats.teams[team.team_id].to_dict(),
        }

    def snapshot(self) -> dict[str, object]:
        """Return the current interpreted match state as a JSON-friendly dict."""
        event = self.last_event
        return {
            "match_id": self.metadata.match_id,
            "period": event.period if event else None,
            "minute": event.minute if event else None,
            "match_second": event.match_second if event else None,
            "score": {"home": event.score_home, "away": event.score_away} if event else {"home": 0, "away": 0},
            "home": self._team_block(Side.HOME),
            "away": self._team_block(Side.AWAY),
            "rhythm": self.last_reading.to_dict() if self.last_reading else None,
            "players": {pid: p.to_dict() for pid, p in self.stats.players.items()},
            "moments": [m.to_dict() for m in self.moments],
            "threat_leaders": [leader.to_dict() for leader in
                               threat_leaders(self.stats.players.values(), THREAT_LEADERS_IN_SNAPSHOT)],
            "shape": self.shape_readings(),
        }

    def shape_readings(self) -> dict[str, dict[str, object] | None]:
        """Each side's current shape reading ("home" and "away"), None until it has enough samples."""
        readings = {side: self.shape.reading(self.metadata.team(side).team_id) for side in (Side.HOME, Side.AWAY)}
        return {side.value: reading.to_dict() if reading else None for side, reading in readings.items()}

    def shape_studio(self) -> dict[str, object]:
        """The whole match's line-height timeline and every shape shift, for the studio chart."""
        shifts = [{"moment_id": m.moment_id, "minute_label": m.minute_label, "period": m.period,
                   "match_second": m.match_second, "team_id": m.team_id, "direction": m.facts["direction"],
                   "line_before_m": m.facts["line_before_m"], "line_after_m": m.facts["line_after_m"]}
                  for m in self.moments if m.kind is MomentKind.SHAPE_SHIFT]
        return {"timeline": [point.to_dict() for point in self.shape.timeline()], "shifts": shifts}
