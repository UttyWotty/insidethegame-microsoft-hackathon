"""Tests for synthetic 22-player tracking.

They check frame completeness and bounds, that event actors reach the ball, team shape by phase, that nobody
runs faster than a human, that sprint tags are occasional, and that distance covered is football-realistic.
They also check the game-state protect drop: a side leading late defends deeper out of possession, and only then.
Keeper tests pin keeper_spot (narrowing the angle within 20 m, the old formula beyond) and the set against a strike.
"""

import math
from collections import defaultdict

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import Point, distance, mirror
from insidegame.domain.enums import EventType, Position, Side
from insidegame.domain.events import MatchEvent
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from insidegame.simulation.probabilities import PROTECT_START_SECOND
from insidegame.tracking.game_state import PROTECT_DROP_M, protect_drop_m
from insidegame.tracking.keeper import KEEPER_NARROW_FRACTION, KEEPER_NARROW_RANGE_M, OWN_GOAL_CENTER, keeper_spot
from insidegame.tracking.model import CLOSE_DOWN_M, LOOKAHEAD_EVENTS, TrackingModel
from insidegame.tracking.motion import SPRINT_KMH

PLAYERS = 22
DISTANCE_KM_RANGE = (8.0, 14.0)
MAX_RUNNING_SPEED_MS = 9.0
HUMAN_TOP_SPEED_KMH = 36.0
ROUNDING_SLACK_M = 0.15
KMH_PER_MS = 3.6
ACTOR_LAG_P90_M = 6.0
SPRINT_FRAME_SHARE = (0.03, 0.2)


def _run() -> tuple[object, list, list]:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    model = TrackingModel(result.metadata)
    frames, sprints = [], []
    for index, event in enumerate(result.events):
        frames.append(model.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS]))
        sprints.append(model.sprint)
    return result, frames, sprints


def _frames() -> tuple[object, list]:
    result, frames, _ = _run()
    return result, frames


def test_every_frame_has_all_players_on_the_pitch() -> None:
    _, frames = _frames()
    for frame in frames:
        assert len(frame) == PLAYERS
        assert all(0 <= x <= PITCH_LENGTH_M and 0 <= y <= PITCH_WIDTH_M for _, x, y in frame)


def test_event_actors_are_on_or_close_to_the_ball() -> None:
    result, frames = _frames()
    lags = []
    for event, frame in zip(result.events, frames, strict=True):
        if event.player_id and event.start and event.team_id:
            home = result.metadata.side_of(event.team_id) is Side.HOME
            spot = event.start if home else mirror(event.start)
            positions = {pid: Point(x, y) for pid, x, y in frame}
            lags.append(distance(positions[event.player_id], spot))
    lags.sort()
    assert lags[len(lags) // 2] < 1.0 and lags[int(0.9 * len(lags))] < ACTOR_LAG_P90_M


def test_nobody_runs_faster_than_a_human_and_sprint_tags_are_occasional() -> None:
    result, frames, sprints = _run()
    for previous, current, event, before in zip(frames, frames[1:], result.events[1:], result.events, strict=False):
        if event.period != before.period or event.event_type is EventType.KICK_OFF:
            continue
        elapsed = event.match_second - before.match_second
        prior = {pid: (x, y) for pid, x, y in previous}
        for pid, x, y in current:
            step = math.hypot(x - prior[pid][0], y - prior[pid][1])
            assert step <= HUMAN_TOP_SPEED_KMH / KMH_PER_MS * elapsed + ROUNDING_SLACK_M
    tagged = [s for s in sprints if s is not None]
    assert SPRINT_FRAME_SHARE[0] <= len(tagged) / len(sprints) <= SPRINT_FRAME_SHARE[1]
    assert all(SPRINT_KMH <= kmh <= HUMAN_TOP_SPEED_KMH for _, kmh in tagged)


def test_goalkeepers_stay_near_their_own_goals() -> None:
    result, frames = _frames()
    home_keeper, away_keeper = result.metadata.home.players[0].player_id, result.metadata.away.players[0].player_id
    for frame in frames[::50]:
        positions = {pid: x for pid, x, _ in frame}
        assert positions[home_keeper] < 25 and positions[away_keeper] > PITCH_LENGTH_M - 25


def test_distance_covered_is_realistic() -> None:
    result, frames = _frames()
    covered: dict[str, float] = defaultdict(float)
    for previous, current, event, before in zip(frames, frames[1:], result.events[1:], result.events, strict=False):
        elapsed = event.match_second - before.match_second
        if event.period != before.period or elapsed <= 0:
            continue
        prior = {pid: (x, y) for pid, x, y in previous}
        for pid, x, y in current:
            step = math.hypot(x - prior[pid][0], y - prior[pid][1])
            covered[pid] += min(step, MAX_RUNNING_SPEED_MS * elapsed)
    outfield = sorted(v / 1000 for pid, v in covered.items() if not pid.endswith("-01"))
    median = outfield[len(outfield) // 2]
    assert DISTANCE_KM_RANGE[0] <= median <= DISTANCE_KM_RANGE[1]


def test_physical_stats_report_distance_and_top_speed() -> None:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    model = TrackingModel(result.metadata)
    for index, event in enumerate(result.events):
        model.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
    physical = model.physical()
    outfield = [v for pid, v in physical.items() if not pid.endswith("-01")]
    assert len(physical) == PLAYERS and all(v["top_kmh"] <= HUMAN_TOP_SPEED_KMH for v in physical.values())
    assert DISTANCE_KM_RANGE[0] <= sorted(v["distance_km"] for v in outfield)[len(outfield) // 2] <= DISTANCE_KM_RANGE[1]


DROP_TOLERANCE_M = 1.0
LATE_SECOND = 4500.0
EARLY_SECOND = 3600.0
OWN_HALF_BALL = Point(20.0, 34.0)


def test_protect_drop_applies_only_when_leading_at_or_after_seventy_minutes() -> None:
    assert protect_drop_m(1, PROTECT_START_SECOND) == PROTECT_DROP_M == 10.0
    assert protect_drop_m(2, LATE_SECOND) == PROTECT_DROP_M
    assert protect_drop_m(1, PROTECT_START_SECOND - 1.0) == 0.0
    assert protect_drop_m(0, LATE_SECOND) == 0.0 and protect_drop_m(-1, LATE_SECOND) == 0.0


def _fresh_frame(second: float, score: tuple[int, int]) -> dict[str, tuple[float, float]]:
    """One frame from a fresh model: home passes in its own half, so the away side is out of possession."""
    metadata = build_fixture("kestrel_bay", "ironvale", 7)
    passer = metadata.home.players_in(Position.MIDFIELDER)[0].player_id
    event = MatchEvent("e1", metadata.match_id, 1, 2, second, EventType.PASS, metadata.home.team_id, passer, 1,
                       OWN_HALF_BALL, score[0], score[1])
    return {pid: (x, y) for pid, x, y in TrackingModel(metadata).frame(event)}


def test_a_leading_side_defends_deeper_out_of_possession_only() -> None:
    metadata = build_fixture("kestrel_bay", "ironvale", 7)
    level, away_leads, home_leads = (_fresh_frame(LATE_SECOND, s) for s in ((0, 0), (0, 1), (1, 0)))
    away_defenders = [p.player_id for p in metadata.away.players_in(Position.DEFENDER)]
    for pid in away_defenders:
        deeper = away_leads[pid][0] - level[pid][0]
        assert abs(deeper - PROTECT_DROP_M) <= DROP_TOLERANCE_M, pid
    keeper = metadata.away.goalkeeper().player_id
    assert away_leads[keeper] == level[keeper]
    assert home_leads == level
    assert _fresh_frame(EARLY_SECOND, (0, 1)) == _fresh_frame(EARLY_SECOND, (0, 0))


KEEPER_TOLERANCE_M = 1e-9
FAR_BALL = Point(52.5, 34.0)
FAR_KEEPER = Point(8.2, 34.0)
CLOSE_BALLS = (Point(6.0, 34.0), Point(10.0, 20.0), Point(15.0, 45.0), Point(1.0, 30.0))
STRIKE = Point(96.0, 31.4)


def test_keeper_spot_narrows_the_angle_on_the_goal_to_ball_line_inside_the_range() -> None:
    for ball in CLOSE_BALLS:
        spot = keeper_spot(ball)
        expected = Point(OWN_GOAL_CENTER.x + (ball.x - OWN_GOAL_CENTER.x) * KEEPER_NARROW_FRACTION,
                         OWN_GOAL_CENTER.y + (ball.y - OWN_GOAL_CENTER.y) * KEEPER_NARROW_FRACTION)
        assert distance(spot, expected) <= KEEPER_TOLERANCE_M
        assert distance(spot, OWN_GOAL_CENTER) < distance(ball, OWN_GOAL_CENTER)
        assert OWN_GOAL_CENTER.x < spot.x < ball.x


def test_keeper_spot_keeps_the_old_formula_beyond_the_range() -> None:
    spot = keeper_spot(FAR_BALL)
    assert abs(spot.x - FAR_KEEPER.x) <= KEEPER_TOLERANCE_M and abs(spot.y - FAR_KEEPER.y) <= KEEPER_TOLERANCE_M


def test_keeper_spot_uses_the_narrow_rule_at_exactly_the_range() -> None:
    ball = Point(OWN_GOAL_CENTER.x + KEEPER_NARROW_RANGE_M, OWN_GOAL_CENTER.y)
    spot = keeper_spot(ball)
    assert abs(spot.x - KEEPER_NARROW_RANGE_M * KEEPER_NARROW_FRACTION) <= KEEPER_TOLERANCE_M
    assert spot.y == OWN_GOAL_CENTER.y


def test_keeper_sets_against_the_strike_not_where_the_shot_ends() -> None:
    metadata = build_fixture("kestrel_bay", "ironvale", 7)
    shooter = metadata.home.players_in(Position.FORWARD)[0].player_id
    shot = MatchEvent("s1", metadata.match_id, 1, 1, 600.0, EventType.SHOT, metadata.home.team_id, shooter, 1,
                      STRIKE, 0, 0, end=Point(PITCH_LENGTH_M, OWN_GOAL_CENTER.y))
    positions = {pid: Point(x, y) for pid, x, y in TrackingModel(metadata).frame(shot)}
    keeper = positions[metadata.away.goalkeeper().player_id]
    expected = mirror(keeper_spot(mirror(STRIKE)))
    assert distance(keeper, expected) <= CLOSE_DOWN_M
    assert STRIKE.x < keeper.x < PITCH_LENGTH_M
