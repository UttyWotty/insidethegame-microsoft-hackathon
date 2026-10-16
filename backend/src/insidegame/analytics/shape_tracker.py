"""Stateful, deterministic tracker of each team's out-of-possession shape and its sustained line-height shifts.

ShapeTracker samples both teams' shapes from the tracked positions before each event, keeps rolling readings and a
per-minute line-height timeline, and compares the last SHAPE_WINDOW_S with the window before it to detect a
significant back-line shift that holds for SHIFT_SUSTAIN_S, outside a per-team cooldown.
Each shift carries before and after window summaries of line height, length, width, space control, and possession
time, plus the score and the latest goal of the period, so the shift can be explained with evidence.
"""

import math
import statistics
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.analytics.shape import SHAPE_DECIMALS, ShapeMetrics, team_shape
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.studio.control import PERCENT, space_control

SHAPE_WINDOW_S: float = 600.0
SHAPE_READING_WINDOW_S: float = 300.0
SHIFT_MIN_M: float = 6.0
SHIFT_SUSTAIN_S: float = 240.0
SHIFT_COOLDOWN_S: float = 900.0
MIN_WINDOW_SAMPLES: int = 15
COVERAGE_SLACK_S: float = 60.0
CONTROL_SAMPLE_S: float = 30.0
SHAPE_TIMELINE_SAMPLE_S: float = 60.0
PERCENT_DECIMALS: int = 1
POSSESSION_EVENTS: frozenset[EventType] = frozenset({EventType.KICK_OFF, EventType.POSSESSION_CHANGE})

ShapeSample = tuple[float, ShapeMetrics]


class ShiftDirection(StrEnum):
    """Which way a team's back line moved."""

    DROPPED = "dropped"
    PUSHED_UP = "pushed_up"


@dataclass(frozen=True)
class WindowSummary:
    """Mean shape, space control, and possession of one team over one comparison window.

    control_pct and possession_pct are None when the window holds no control samples or no possession time.
    """

    line_height_m: float
    length_m: float
    width_m: float
    control_pct: float | None
    possession_pct: float | None
    samples: int


@dataclass(frozen=True)
class ShapeShift:
    """A sustained, significant change in a team's back-line height between two consecutive windows.

    last_goal is (scoring team_id, match_second, score_home, score_away) for the latest goal of the period within
    2 * window_s before the shift, or None.
    """

    team_id: str
    opponent_id: str
    direction: ShiftDirection
    period: int
    match_second: float
    before: WindowSummary
    after: WindowSummary
    window_s: float
    score_home: int
    score_away: int
    last_goal: tuple[str, float, int, int] | None

    @property
    def line_change_m(self) -> float:
        """Absolute change in back-line height, in metres."""
        return abs(self.after.line_height_m - self.before.line_height_m)


@dataclass(frozen=True)
class TeamShapeReading:
    """A team's smoothed shape over the last SHAPE_READING_WINDOW_S out of possession."""

    team_id: str
    metrics: ShapeMetrics
    samples: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation with the metrics, sample count, and window length."""
        return {"team_id": self.team_id, **self.metrics.to_dict(), "samples": self.samples,
                "window_minutes": int(SHAPE_READING_WINDOW_S // SECONDS_PER_MINUTE)}


@dataclass(frozen=True)
class ShapeTimelinePoint:
    """Both teams' smoothed back-line heights at one minute; None when a team has no reading yet."""

    period: int
    match_second: float
    minute: int
    home_line_m: float | None
    away_line_m: float | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"period": self.period, "match_second": self.match_second, "minute": self.minute,
                "home_line_m": None if self.home_line_m is None else round(self.home_line_m, SHAPE_DECIMALS),
                "away_line_m": None if self.away_line_m is None else round(self.away_line_m, SHAPE_DECIMALS)}


def _mean_metrics(samples: list[ShapeMetrics]) -> ShapeMetrics:
    return ShapeMetrics(statistics.fmean(s.line_height_m for s in samples), statistics.fmean(s.length_m for s in samples),
                        statistics.fmean(s.width_m for s in samples), statistics.fmean(s.compactness_m for s in samples))


@dataclass
class ShapeTracker:
    """Observes events with the positions before them and reports line-height shifts.

    Defaults: every buffer starts empty, nobody has possession, and no shift has fired.
    """

    metadata: MatchMetadata
    samples: dict[str, deque[ShapeSample]] = field(default_factory=dict)
    control: deque[tuple[float, float]] = field(default_factory=deque)
    possession: deque[tuple[float, str, float]] = field(default_factory=deque)
    possessing: str | None = None
    last_second: float | None = None
    last_control_s: float | None = None
    sustain: dict[str, tuple[ShiftDirection, float]] = field(default_factory=dict)
    last_shift_s: dict[str, float] = field(default_factory=dict)
    goals: list[tuple[int, str, float, int, int]] = field(default_factory=list)
    points: list[ShapeTimelinePoint] = field(default_factory=list)
    now: float = 0.0
    home_ids: frozenset[str] = field(init=False)
    match_ids: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        self.samples = {team.team_id: deque() for team in self._teams()}
        self.home_ids = frozenset(p.player_id for p in self.metadata.home.players)
        self.match_ids = self.home_ids | frozenset(p.player_id for p in self.metadata.away.players)

    def _teams(self) -> tuple[Team, Team]:
        return self.metadata.home, self.metadata.away

    def _reset_period(self, event: MatchEvent) -> None:
        for buffer in self.samples.values():
            buffer.clear()
        self.control.clear()
        self.possession.clear()
        self.sustain.clear()
        self.last_shift_s.clear()
        self.possessing, self.last_second, self.last_control_s = None, event.match_second, None

    def observe(self, event: MatchEvent, positions_before: Mapping[str, Point] | None) -> tuple[ShapeShift, ...]:
        """Record one event and the frame before it; return the shifts it completes (usually none).

        positions_before (None or an empty mapping adds no samples) is the absolute home-frame positions after the previous event.
        """
        self.now = event.match_second
        if event.event_type is EventType.PERIOD_START:
            self._reset_period(event)
            return ()
        self._track_possession(event)
        if positions_before and self.possessing is not None:
            self._sample(event, positions_before)
        if event.event_type in POSSESSION_EVENTS and event.team_id:
            self.possessing = event.team_id
        if event.event_type is EventType.GOAL and event.team_id:
            self.goals.append((event.period, event.team_id, event.match_second, event.score_home, event.score_away))
        self._expire(event.match_second)
        return tuple(shift for team in self._teams() if (shift := self._detect(team, event)) is not None)

    def _track_possession(self, event: MatchEvent) -> None:
        """Attribute the time since the last event to the team that had the ball, as StatsAccumulator does."""
        if self.possessing is not None and self.last_second is not None:
            self.possession.append((event.match_second, self.possessing, event.match_second - self.last_second))
        self.last_second = event.match_second

    def _sample(self, event: MatchEvent, positions: Mapping[str, Point]) -> None:
        """Add out-of-possession shape samples, a throttled space-control sample, and a timeline point."""
        second = event.match_second
        for team in self._teams():
            if team.team_id != self.possessing:
                metrics = team_shape(team, positions, team is self.metadata.home)
                if metrics is not None:
                    self.samples[team.team_id].append((second, metrics))
        if self.last_control_s is None or second - self.last_control_s >= CONTROL_SAMPLE_S:
            frame = [(pid, p.x, p.y) for pid, p in positions.items()
                     if pid in self.match_ids and math.isfinite(p.x) and math.isfinite(p.y)]
            if frame:
                self.control.append((second, space_control(frame, self.home_ids).home_share))
                self.last_control_s = second
        last = self.points[-1] if self.points else None
        if last is None or last.period != event.period or second - last.match_second >= SHAPE_TIMELINE_SAMPLE_S:
            home, away = (self.reading(team.team_id) for team in self._teams())
            self.points.append(ShapeTimelinePoint(event.period, second, event.minute,
                                                  home.metrics.line_height_m if home else None,
                                                  away.metrics.line_height_m if away else None))

    def _expire(self, second: float) -> None:
        oldest = second - 2 * SHAPE_WINDOW_S
        for buffer in (*self.samples.values(), self.control, self.possession):
            while buffer and buffer[0][0] < oldest:
                buffer.popleft()

    def _window(self, team: Team, start: float, end: float, include_end: bool) -> WindowSummary:
        """Summarise samples with start <= second < end, or <= end when include_end (the window ending now)."""
        def inside(second: float) -> bool:
            return start <= second < end or (include_end and second == end)

        shapes = [m for s, m in self.samples[team.team_id] if inside(s)]
        mean = _mean_metrics(shapes)
        shares = [share if team is self.metadata.home else PERCENT - share for s, share in self.control if inside(s)]
        total = sum(dt for s, _, dt in self.possession if inside(s))
        held = sum(dt for s, owner, dt in self.possession if inside(s) and owner == team.team_id)
        return WindowSummary(mean.line_height_m, mean.length_m, mean.width_m,
                             statistics.fmean(shares) if shares else None,
                             PERCENT * held / total if total else None, len(shapes))

    def _windows_ready(self, team: Team, second: float) -> bool:
        buffer = self.samples[team.team_id]
        if not buffer or buffer[0][0] > second - 2 * SHAPE_WINDOW_S + COVERAGE_SLACK_S:
            return False
        split = second - SHAPE_WINDOW_S
        after = sum(1 for s, _ in buffer if s >= split)
        return after >= MIN_WINDOW_SAMPLES and len(buffer) - after >= MIN_WINDOW_SAMPLES

    def _detect(self, team: Team, event: MatchEvent) -> ShapeShift | None:
        """Track the sustained-change condition for one team and fire a shift when it has held long enough."""
        second = event.match_second
        if not self._windows_ready(team, second):
            self.sustain.pop(team.team_id, None)
            return None
        buffer = self.samples[team.team_id]
        split = second - SHAPE_WINDOW_S
        before = statistics.fmean(m.line_height_m for s, m in buffer if s < split)
        after = statistics.fmean(m.line_height_m for s, m in buffer if s >= split)
        if abs(after - before) < SHIFT_MIN_M:
            self.sustain.pop(team.team_id, None)
            return None
        direction = ShiftDirection.DROPPED if after < before else ShiftDirection.PUSHED_UP
        held = self.sustain.get(team.team_id)
        since = held[1] if held is not None and held[0] is direction else second
        self.sustain[team.team_id] = (direction, since)
        last = self.last_shift_s.get(team.team_id)
        if second - since < SHIFT_SUSTAIN_S or (last is not None and second - last < SHIFT_COOLDOWN_S):
            return None
        self.last_shift_s[team.team_id] = second
        self.sustain.pop(team.team_id, None)
        return self._shift(team, event, direction)

    def _shift(self, team: Team, event: MatchEvent, direction: ShiftDirection) -> ShapeShift:
        second = event.match_second
        opponent = self.metadata.away if team is self.metadata.home else self.metadata.home
        recent = [g for g in self.goals if g[0] == event.period and second - g[2] <= 2 * SHAPE_WINDOW_S]
        last_goal = (recent[-1][1], recent[-1][2], recent[-1][3], recent[-1][4]) if recent else None
        return ShapeShift(team.team_id, opponent.team_id, direction, event.period, second,
                          self._window(team, second - 2 * SHAPE_WINDOW_S, second - SHAPE_WINDOW_S, False),
                          self._window(team, second - SHAPE_WINDOW_S, second, True), SHAPE_WINDOW_S,
                          event.score_home, event.score_away, last_goal)

    def reading(self, team_id: str) -> TeamShapeReading | None:
        """The team's mean shape over the last SHAPE_READING_WINDOW_S.

        Returns None below MIN_WINDOW_SAMPLES samples or for a team id that is not in this match.
        """
        buffer = self.samples.get(team_id)
        if buffer is None:
            return None
        recent = [m for s, m in buffer if s >= self.now - SHAPE_READING_WINDOW_S]
        if len(recent) < MIN_WINDOW_SAMPLES:
            return None
        return TeamShapeReading(team_id, _mean_metrics(recent), len(recent))

    def timeline(self) -> list[ShapeTimelinePoint]:
        """Both teams' smoothed line heights, about once per SHAPE_TIMELINE_SAMPLE_S, for the whole match."""
        return list(self.points)
