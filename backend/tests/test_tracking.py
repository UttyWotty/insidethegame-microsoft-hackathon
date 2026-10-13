"""Tests for synthetic 22-player tracking.

They check frame completeness and bounds, that event actors reach the ball, team shape by phase, that nobody
runs faster than a human, that sprint tags are occasional, and that distance covered is football-realistic.
"""

import math
from collections import defaultdict

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import Point, distance, mirror
from insidegame.domain.enums import EventType, Side
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, TrackingModel
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
