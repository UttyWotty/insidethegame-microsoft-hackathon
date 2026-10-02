"""Rolling-window model of game rhythm: momentum, control, and chaos.

Momentum compares each side's attacking threat over the last few minutes, from -1 (away) to +1 (home).
Chaos measures turnover frequency above a typical-match baseline, and control measures each side's share of completed passes.
"""

from collections import deque
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from insidegame.analytics.pass_quality import PassQuality
from insidegame.core.constants import PITCH_LENGTH_M, SECONDS_PER_MINUTE
from insidegame.domain.enums import EventType, Outcome, Side
from insidegame.domain.events import MatchEvent

WINDOW_SECONDS: float = 300.0
MIN_WINDOW_SECONDS: float = 60.0
THREAT_XG_WEIGHT: float = 1.0
THREAT_FINAL_THIRD_WEIGHT: float = 0.03
THREAT_HIGH_PRESSURE_WEIGHT: float = 0.01
HIGH_PRESSURE_LINE_M: float = PITCH_LENGTH_M / 2
CHAOS_BASELINE_TURNOVERS_PER_MIN: float = 3.0
CHAOS_TURNOVERS_PER_MIN_SPAN: float = 1.5
MOMENTUM_EPSILON: float = 1e-6

CHAOS_STATE_THRESHOLD: float = 0.6
PRESSURE_STATE_THRESHOLD: float = 0.35
CONTROL_STATE_THRESHOLD: float = 0.65
NEUTRAL_SHARE: float = 0.5
READING_DECIMALS: int = 3


class RhythmState(StrEnum):
    """Plain-language label for the current phase of play."""

    BALANCED = "balanced"
    HOME_CONTROL = "home_control"
    AWAY_CONTROL = "away_control"
    HOME_PRESSURE = "home_pressure"
    AWAY_PRESSURE = "away_pressure"
    CHAOS = "chaos"


@dataclass(frozen=True)
class RhythmReading:
    """Rhythm metrics over the trailing window."""

    momentum: float
    home_threat: float
    away_threat: float
    chaos: float
    turnovers_per_minute: float
    home_pass_share: float
    state: RhythmState

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        data = {k: round(v, READING_DECIMALS) if isinstance(v, float) else v for k, v in asdict(self).items()}
        data["state"] = self.state.value
        return data


@dataclass(frozen=True)
class _Sample:
    second: float
    side: Side | None
    threat: float
    turnover: bool
    completed_pass: bool


def _threat(event: MatchEvent, xg: float | None, quality: PassQuality | None) -> float:
    if event.event_type is EventType.SHOT and xg is not None:
        return THREAT_XG_WEIGHT * xg
    if event.event_type is EventType.PASS and quality and quality.final_third_entry and event.outcome is Outcome.SUCCESS:
        return THREAT_FINAL_THIRD_WEIGHT
    if event.event_type is EventType.PRESSURE and event.start and event.start.x >= HIGH_PRESSURE_LINE_M:
        return THREAT_HIGH_PRESSURE_WEIGHT
    return 0.0


def _classify(momentum: float, chaos: float, home_share: float) -> RhythmState:
    if chaos >= CHAOS_STATE_THRESHOLD:
        return RhythmState.CHAOS
    if momentum >= PRESSURE_STATE_THRESHOLD:
        return RhythmState.HOME_PRESSURE
    if momentum <= -PRESSURE_STATE_THRESHOLD:
        return RhythmState.AWAY_PRESSURE
    if home_share >= CONTROL_STATE_THRESHOLD:
        return RhythmState.HOME_CONTROL
    if home_share <= 1.0 - CONTROL_STATE_THRESHOLD:
        return RhythmState.AWAY_CONTROL
    return RhythmState.BALANCED


@dataclass
class RhythmTracker:
    """Maintains the trailing window and produces a reading after each event."""

    samples: deque[_Sample] = field(default_factory=deque)
    period_start: float = 0.0

    def update(self, event: MatchEvent, side: Side | None, xg: float | None, quality: PassQuality | None) -> RhythmReading:
        """Add an event to the window and return the current rhythm reading."""
        if event.event_type is EventType.PERIOD_START:
            self.samples.clear()
            self.period_start = event.match_second
        completed = event.event_type is EventType.PASS and event.outcome is Outcome.SUCCESS
        turnover = event.event_type is EventType.POSSESSION_CHANGE
        self.samples.append(_Sample(event.match_second, side, _threat(event, xg, quality), turnover, completed))
        while self.samples and self.samples[0].second < event.match_second - WINDOW_SECONDS:
            self.samples.popleft()
        return self._reading(event.match_second)

    def _reading(self, now: float) -> RhythmReading:
        home = sum(s.threat for s in self.samples if s.side is Side.HOME)
        away = sum(s.threat for s in self.samples if s.side is Side.AWAY)
        momentum = (home - away) / (home + away + MOMENTUM_EPSILON)
        span_minutes = max(min(WINDOW_SECONDS, now - self.period_start), MIN_WINDOW_SECONDS) / SECONDS_PER_MINUTE
        turnovers_pm = sum(s.turnover for s in self.samples) / span_minutes
        chaos = min(max((turnovers_pm - CHAOS_BASELINE_TURNOVERS_PER_MIN) / CHAOS_TURNOVERS_PER_MIN_SPAN, 0.0), 1.0)
        home_passes = sum(s.completed_pass for s in self.samples if s.side is Side.HOME)
        all_passes = sum(s.completed_pass for s in self.samples)
        share = home_passes / all_passes if all_passes else NEUTRAL_SHARE
        return RhythmReading(momentum, home, away, chaos, turnovers_pm, share, _classify(momentum, chaos, share))
