"""Streaming facade for pipeline stage two, turning each raw event into interpreted output.

MatchAnalyzer.ingest computes xG, pass quality, and a broadcast shot card, updates statistics and rhythm, and
detects key moments.
snapshot returns the full machine-readable match state for overlays, agents, and APIs.
"""

from dataclasses import dataclass, field

from insidegame.analytics.detectors import MomentDetector
from insidegame.analytics.moments import KeyMoment
from insidegame.analytics.pass_quality import PassQuality, assess_pass
from insidegame.analytics.rhythm import RhythmReading, RhythmTracker
from insidegame.analytics.shot_card import ShotCard, shot_card
from insidegame.analytics.stats import StatsAccumulator
from insidegame.analytics.xg import expected_goals
from insidegame.domain.enums import EventType, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

POSSESSION_DECIMALS: int = 1


@dataclass(frozen=True)
class AnalysisUpdate:
    """Everything stage two derived from a single event.

    Defaults: shot is None except on shot events.
    """

    event: MatchEvent
    xg: float | None
    pass_quality: PassQuality | None
    rhythm: RhythmReading
    moments: tuple[KeyMoment, ...]
    shot: ShotCard | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "event": self.event.to_dict(),
            "xg": self.xg,
            "pass_quality": self.pass_quality.to_dict() if self.pass_quality else None,
            "rhythm": self.rhythm.to_dict(),
            "moments": [m.to_dict() for m in self.moments],
            "shot": self.shot.to_dict() if self.shot else None,
        }


@dataclass
class MatchAnalyzer:
    """Stateful, I/O-free interpreter for one match's event stream."""

    metadata: MatchMetadata
    stats: StatsAccumulator = field(init=False)
    rhythm: RhythmTracker = field(default_factory=RhythmTracker)
    detector: MomentDetector = field(init=False)
    moments: list[KeyMoment] = field(default_factory=list)
    last_event: MatchEvent | None = None
    last_reading: RhythmReading | None = None

    def __post_init__(self) -> None:
        self.stats = StatsAccumulator(self.metadata)
        self.detector = MomentDetector(self.metadata)

    def ingest(self, event: MatchEvent) -> AnalysisUpdate:
        """Interpret one event and return the derived update."""
        xg = expected_goals(event.start, event.under_pressure) if (
            event.event_type is EventType.SHOT and event.start) else None
        quality = assess_pass(event.start, event.end, event.under_pressure) if (
            event.event_type is EventType.PASS and event.start and event.end) else None
        side = self.metadata.side_of(event.team_id) if event.team_id else None
        self.stats.apply(event, xg, quality)
        reading = self.rhythm.update(event, side, xg, quality)
        new_moments = tuple(self.detector.detect(event, xg, quality, reading))
        self.moments.extend(new_moments)
        self.last_event, self.last_reading = event, reading
        card = shot_card(event, xg) if xg is not None else None
        return AnalysisUpdate(event, xg, quality, reading, new_moments, card)

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
        }
