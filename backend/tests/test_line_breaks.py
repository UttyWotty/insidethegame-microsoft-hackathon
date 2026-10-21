"""Tests for the pure line-break assessment and its use in per-event threat assessment.

Opponent positions are placed by hand in the absolute home frame, so every count can be checked exactly.
They cover bypass counting, strict line breaks, goalkeeper and teammate exclusion, away mirroring, and the None paths.
"""

import pytest

from insidegame.analytics.line_breaks import DefensiveLine, assess_line_break, opponent_lines, opponents_goal_side
from insidegame.analytics.threat import assess_threat
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import EventType, Outcome, Position
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.simulation.roster import build_fixture

LINE_X: dict[Position, float] = {Position.GOALKEEPER: 100.0, Position.DEFENDER: 80.0, Position.MIDFIELDER: 60.0,
                                 Position.FORWARD: 40.0}
SPREAD_M = 2.0
WIDTH_STEP_M = 12.0


@pytest.fixture(scope="module")
def metadata() -> MatchMetadata:
    return build_fixture("kestrel_bay", "ironvale", 1)


def _line_shape(team: Team) -> dict[str, Point]:
    """A team set in lines as seen by the opponent attacking toward x = 105 (defenders at x 79 to 81, and so on)."""
    positions: dict[str, Point] = {}
    for index, player in enumerate(team.players):
        offset = SPREAD_M * (index % 2) - SPREAD_M / 2
        positions[player.player_id] = Point(LINE_X[player.position] + offset, WIDTH_STEP_M * (index % 5) + 6.0)
    return positions


def _away_shape(metadata: MatchMetadata) -> dict[str, Point]:
    """Away players in lines, in the absolute home frame."""
    return _line_shape(metadata.away)


def _with_home_team(metadata: MatchMetadata, positions: dict[str, Point]) -> dict[str, Point]:
    """Add every home player far upfield, where they would count if teammates were not excluded."""
    return positions | {p.player_id: Point(104.0, 34.0) for p in metadata.home.players}


def _pass(team_id: str, player_id: str, start: Point | None, end: Point | None,
          outcome: Outcome = Outcome.SUCCESS, kind: EventType = EventType.PASS) -> MatchEvent:
    return MatchEvent("e1", "m", 1, 1, 100.0, kind, team_id, player_id, 1, start, 0, 0, end=end, outcome=outcome,
                      receiver_id=None)


def test_goalkeeper_and_teammates_are_never_counted(metadata: MatchMetadata) -> None:
    lines = opponent_lines(metadata.home.team_id, metadata, _with_home_team(metadata, _away_shape(metadata)))
    assert Position.GOALKEEPER not in lines
    assert sum(len(points) for points in lines.values()) == len(metadata.away.players) - 1
    assert opponents_goal_side(90.0, lines) == 0


def test_bypassed_counts_goal_side_opponents_before_minus_after(metadata: MatchMetadata) -> None:
    lines = opponent_lines(metadata.home.team_id, metadata, _away_shape(metadata))
    forward_pass = assess_line_break(Point(50.0, 30.0), Point(70.0, 30.0), lines)
    assert forward_pass is not None and forward_pass.opponents_bypassed == 3
    backward = assess_line_break(Point(70.0, 30.0), Point(50.0, 30.0), lines)
    assert backward is not None and backward.opponents_bypassed == 0 and not backward.breaks_line


def test_a_line_breaks_only_from_behind_every_player_to_beyond_every_one(metadata: MatchMetadata) -> None:
    lines = opponent_lines(metadata.home.team_id, metadata, _away_shape(metadata))
    both = assess_line_break(Point(50.0, 30.0), Point(90.0, 30.0), lines)
    assert both is not None and both.lines_broken == (DefensiveLine.MIDFIELD, DefensiveLine.DEFENCE)
    assert both.opponents_bypassed == 7
    midfield = assess_line_break(Point(50.0, 30.0), Point(70.0, 30.0), lines)
    assert midfield is not None and midfield.lines_broken == (DefensiveLine.MIDFIELD,)
    inside_the_line = assess_line_break(Point(60.0, 30.0), Point(75.0, 30.0), lines)
    assert inside_the_line is not None and not inside_the_line.breaks_line
    short_of_the_last_defender = assess_line_break(Point(70.0, 30.0), Point(80.5, 30.0), lines)
    assert short_of_the_last_defender is not None and not short_of_the_last_defender.breaks_line


def test_away_passes_see_home_opponents_in_the_away_attacking_frame(metadata: MatchMetadata) -> None:
    home_shape = {pid: mirror(p) for pid, p in _line_shape(metadata.home).items()}
    lines = opponent_lines(metadata.away.team_id, metadata, home_shape)
    result = assess_line_break(Point(50.0, 30.0), Point(90.0, 30.0), lines)
    assert result is not None and result.opponents_bypassed == 7 and result.breaks_line


def test_threat_has_no_line_break_without_positions_or_for_carries(metadata: MatchMetadata) -> None:
    home = metadata.home
    player = home.players[5].player_id
    start, end = Point(50.0, 30.0), Point(90.0, 30.0)
    assert assess_line_break(start, end, {}) is None
    no_positions = assess_threat(_pass(home.team_id, player, start, end), metadata, {})
    assert no_positions is not None and no_positions.line_break is None and not no_positions.breaks_line
    assert no_positions.xt_added > 0
    carry = assess_threat(_pass(home.team_id, player, start, end, kind=EventType.CARRY), metadata,
                          _away_shape(metadata))
    assert carry is not None and carry.line_break is None
    tracked = assess_threat(_pass(home.team_id, player, start, end), metadata, _away_shape(metadata))
    assert tracked is not None and tracked.breaks_line


def test_failed_passes_and_events_without_start_or_end_give_no_threat(metadata: MatchMetadata) -> None:
    home = metadata.home
    player = home.players[5].player_id
    shape = _away_shape(metadata)
    assert assess_threat(_pass(home.team_id, player, Point(50.0, 30.0), Point(90.0, 30.0), Outcome.FAILURE),
                         metadata, shape) is None
    assert assess_threat(_pass(home.team_id, player, None, Point(90.0, 30.0)), metadata, shape) is None
    assert assess_threat(_pass(home.team_id, player, Point(50.0, 30.0), None), metadata, shape) is None
    shot = _pass(home.team_id, player, Point(90.0, 30.0), Point(105.0, 34.0), kind=EventType.SHOT)
    assert assess_threat(shot, metadata, shape) is None


def test_a_pass_starting_or_ending_level_with_a_line_does_not_break_it() -> None:
    lines = {Position.MIDFIELDER: [Point(50.0, 20.0), Point(52.0, 40.0)],
             Position.DEFENDER: [Point(70.0, 10.0), Point(72.0, 50.0)]}
    level_start = assess_line_break(Point(50.0, 0.0), Point(80.0, 0.0), lines)
    level_end = assess_line_break(Point(40.0, 0.0), Point(72.0, 0.0), lines)
    assert level_start is not None and level_start.lines_broken == (DefensiveLine.DEFENCE,)
    assert level_start.opponents_bypassed == 3
    assert level_end is not None and level_end.lines_broken == (DefensiveLine.MIDFIELD,)
    assert assess_line_break(Point(0.0, 0.0), Point(100.0, 0.0), {Position.MIDFIELDER: [], Position.DEFENDER: []}) is None
