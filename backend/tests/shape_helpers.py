"""Shared helpers for shape tests: synthetic positions maps and event streams with a scripted back line.

Positions put the home back line at a chosen height (in its own frame) and the away team at a fixed shape, so shape
metrics and shifts are known in advance without the simulator or the tracking model.
Streams emit one event every STEP_S seconds, and a schedule decides who has the ball and where the home line is.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.analytics.rhythm import RhythmReading, RhythmState
from insidegame.analytics.shape_moments import SHAPE_SHIFT_IMPORTANCE, shape_facts
from insidegame.analytics.shape_tracker import SHAPE_WINDOW_S, ShapeShift, ShapeTracker, ShiftDirection, WindowSummary
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import EventType, Position
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.simulation.roster import build_fixture

STEP_S = 10.0
KEEPER_X = 5.0
LANE_YS = (10.0, 26.0, 42.0, 58.0)
MIDFIELD_GAP_M = 15.0
FORWARD_GAP_M = 30.0
AWAY_LINE_M = 30.0

LineAt = Callable[[float], float]
HomeHasBall = Callable[[float], bool]


def fixture() -> MatchMetadata:
    """Kestrel Bay (home, "kba") against Ironvale ("irv")."""
    return build_fixture("kestrel_bay", "ironvale", 1)


def own_frame_shape(team: Team, line_m: float) -> dict[str, Point]:
    """Own-frame positions: keeper, defenders on the line, midfielders and forwards at fixed gaps in front."""
    positions: dict[str, Point] = {}
    for group, x in ((Position.DEFENDER, line_m), (Position.MIDFIELDER, line_m + MIDFIELD_GAP_M),
                     (Position.FORWARD, line_m + FORWARD_GAP_M)):
        for index, player in enumerate(team.players_in(group)):
            positions[player.player_id] = Point(x, LANE_YS[index % len(LANE_YS)])
    positions[team.goalkeeper().player_id] = Point(KEEPER_X, LANE_YS[1])
    return positions


def positions_for(metadata: MatchMetadata, home_line_m: float, away_line_m: float = AWAY_LINE_M) -> dict[str, Point]:
    """Absolute home-frame positions for both teams at the given own-frame line heights."""
    home = own_frame_shape(metadata.home, home_line_m)
    away = {pid: mirror(p) for pid, p in own_frame_shape(metadata.away, away_line_m).items()}
    return home | away


def event(metadata: MatchMetadata, sequence: int, second: float, kind: EventType, team_id: str | None,
          period: int = 1, score: tuple[int, int] = (0, 0)) -> MatchEvent:
    """A minimal event: no player, no location."""
    return MatchEvent(f"e{sequence}", metadata.match_id, sequence, period, second, kind, team_id, None, sequence, None,
                      score[0], score[1])


@dataclass
class Stream:
    """A scripted match stream fed through a ShapeTracker, keeping the shifts and the frames it saw."""

    metadata: MatchMetadata
    tracker: ShapeTracker
    shifts: list[ShapeShift] = field(default_factory=list)
    events: list[MatchEvent] = field(default_factory=list)
    frames: dict[float, dict[str, Point]] = field(default_factory=dict)
    sustained: bool = False


def run_stream(line_at: LineAt, end_s: float, home_has_ball: HomeHasBall = lambda second: False,
               goals: dict[float, tuple[str, int, int]] | None = None, with_positions: bool = True,
               period_starts: tuple[float, ...] = ()) -> Stream:
    """Feed a scripted first half to a fresh tracker; positions before each event use the line of the previous step.

    goals (default none) maps a second to (scoring team_id, score_home, score_away); period_starts (default none)
    lists seconds at which a second-period PERIOD_START and KICK_OFF arrive.
    """
    metadata = fixture()
    stream = Stream(metadata, ShapeTracker(metadata))
    home, away = metadata.home.team_id, metadata.away.team_id
    score, period, sequence, holder = (0, 0), 1, 0, away
    script = [event(metadata, 0, 0.0, EventType.PERIOD_START, None), event(metadata, 1, 0.0, EventType.KICK_OFF, away)]
    for item in script:
        stream.tracker.observe(item, None)
    second = 0.0
    while second < end_s:
        second += STEP_S
        sequence += 1
        if second in period_starts:
            period = 2
            stream.tracker.observe(event(metadata, sequence, second, EventType.PERIOD_START, None, period, score), None)
            stream.tracker.observe(event(metadata, sequence, second, EventType.KICK_OFF, holder, period, score), None)
            continue
        if goals and second in goals:
            scorer, score_home, score_away = goals[second]
            score = (score_home, score_away)
            kind, team = EventType.GOAL, scorer
        else:
            team = home if home_has_ball(second) else away
            kind = EventType.POSSESSION_CHANGE if team != holder else EventType.PASS
            holder = team
        current = event(metadata, sequence, second, kind, team, period, score)
        frame = positions_for(metadata, line_at(second - STEP_S)) if with_positions else None
        if frame is not None:
            stream.frames[second] = frame
        stream.events.append(current)
        stream.shifts.extend(stream.tracker.observe(current, frame))
        stream.sustained = stream.sustained or bool(stream.tracker.sustain)
    return stream


def step_line(before_m: float, after_m: float, at_s: float) -> LineAt:
    """A home line at before_m that moves to after_m at at_s."""
    return lambda second: before_m if second < at_s else after_m


SHIFT_SECOND = 5280.0
GOAL_SECOND = 4620.0
LEVEL_RHYTHM = RhythmReading(0.0, 0.0, 0.0, 0.0, 0.0, 0.5, RhythmState.BALANCED)


def shape_moment(metadata: MatchMetadata, direction: ShiftDirection, with_trigger: bool) -> KeyMoment:
    """A shape_shift moment for the home side at 89' with known numbers, after a home goal at 78' when with_trigger."""
    deep, high = WindowSummary(20.04, 49.0, 39.5, 46.27, 49.8, 40), WindowSummary(31.12, 50.0, 40.0, 52.0, 65.14, 40)
    before, after = (high, deep) if direction is ShiftDirection.DROPPED else (deep, high)
    goal = (metadata.home.team_id, GOAL_SECOND, 2, 1) if with_trigger else None
    shift = ShapeShift(metadata.home.team_id, metadata.away.team_id, direction, 2, SHIFT_SECOND, before, after,
                       SHAPE_WINDOW_S, 2, 1, goal)
    return KeyMoment(f"shape-{direction.value}-{with_trigger}", MomentKind.SHAPE_SHIFT, 2, SHIFT_SECOND,
                     SHAPE_SHIFT_IMPORTANCE, metadata.home.team_id, (), ("e1",),
                     shape_facts(shift, metadata, LEVEL_RHYTHM))
