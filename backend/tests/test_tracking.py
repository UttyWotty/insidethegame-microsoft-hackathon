"""Tests for synthetic 22-player tracking.

They check frame completeness and bounds, that event actors are placed on the ball, team shape by phase,
and that implied distance covered is football-realistic.
"""

import math
from collections import defaultdict

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.domain.enums import EventType
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import TrackingModel

PLAYERS = 22
DISTANCE_KM_RANGE = (8.0, 14.0)
MAX_RUNNING_SPEED_MS = 9.0


def _frames() -> tuple[object, list]:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    model = TrackingModel(result.metadata)
    return result, [model.frame(event) for event in result.events]


def test_every_frame_has_all_players_on_the_pitch() -> None:
    _, frames = _frames()
    for frame in frames:
        assert len(frame) == PLAYERS
        assert all(0 <= x <= PITCH_LENGTH_M and 0 <= y <= PITCH_WIDTH_M for _, x, y in frame)


def test_carrier_is_placed_where_the_carry_ends() -> None:
    result, frames = _frames()
    index, event = next((i, e) for i, e in enumerate(result.events)
                        if e.event_type is EventType.CARRY and e.team_id == result.metadata.home.team_id)
    positions = {pid: (x, y) for pid, x, y in frames[index]}
    assert math.isclose(positions[event.player_id][0], round(event.end.x, 1), abs_tol=0.11)


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
