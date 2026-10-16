"""Tests for pitch zones and the simulator's weak-flank tendency.

They check channel and third edges, flank mirroring, the lateral shift sign per weak flank, and membership edges.
Over many seeded matches, flank flags must point at the defending club's configured weak flank, proving real signal.
"""

import pytest

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.core.geometry import Point
from insidegame.core.zones import CHANNEL_WIDTH_M, PITCH_THIRD_M, Channel, Third, channel_of, opposite_flank, third_of
from insidegame.domain.teams import TeamStyle
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.flanks import (
    EXPLOIT_START_X_M,
    WEAK_FLANK_LATERAL_SHIFT_M,
    WEAK_FLANK_TACKLE_START_X_M,
    exploited_channel,
    in_exploited_final_third,
    in_exploited_flank,
    lateral_shift,
)
from insidegame.simulation.roster import CLUB_PRESETS, build_fixture

PRECISION_SEEDS = range(1, 31)
MIN_PRECISION = 0.85
FLANK_PATTERNS = frozenset({"flank_exposed", "channel_overload"})
LOW_Y, HIGH_Y = 5.0, 63.0
FINAL_X, MIDDLE_X = 80.0, 60.0


def _style(weak: Channel) -> TeamStyle:
    return TeamStyle(label="test", directness=0.5, pressing=0.5, risk=0.5, weak_flank=weak)


def test_channels_and_thirds_split_at_their_edges() -> None:
    assert channel_of(CHANNEL_WIDTH_M - 0.01) is Channel.LEFT and channel_of(CHANNEL_WIDTH_M) is Channel.CENTRE
    assert channel_of(2 * CHANNEL_WIDTH_M) is Channel.RIGHT
    assert third_of(PITCH_THIRD_M - 0.01) is Third.DEFENSIVE and third_of(PITCH_THIRD_M) is Third.MIDDLE
    assert third_of(2 * PITCH_THIRD_M) is Third.FINAL
    assert [opposite_flank(c) for c in Channel] == [Channel.RIGHT, Channel.CENTRE, Channel.LEFT]


def test_lateral_shift_points_at_the_weak_flank() -> None:
    ball = Point(EXPLOIT_START_X_M, 34.0)
    assert exploited_channel(_style(Channel.LEFT)) is Channel.RIGHT
    assert lateral_shift(ball, _style(Channel.LEFT)) == WEAK_FLANK_LATERAL_SHIFT_M
    assert lateral_shift(ball, _style(Channel.RIGHT)) == -WEAK_FLANK_LATERAL_SHIFT_M
    assert lateral_shift(Point(EXPLOIT_START_X_M - 0.01, 34.0), _style(Channel.LEFT)) == 0.0
    assert lateral_shift(ball, _style(Channel.CENTRE)) == 0.0


def test_exploited_zone_membership_edges() -> None:
    weak_left = _style(Channel.LEFT)  # attackers exploit their own right, high y
    assert in_exploited_final_third(Point(FINAL_X, HIGH_Y), weak_left)
    assert not in_exploited_final_third(Point(MIDDLE_X, HIGH_Y), weak_left)
    assert not in_exploited_final_third(Point(FINAL_X, LOW_Y), weak_left)
    assert in_exploited_flank(Point(WEAK_FLANK_TACKLE_START_X_M, HIGH_Y), weak_left)
    assert not in_exploited_flank(Point(WEAK_FLANK_TACKLE_START_X_M - 0.01, HIGH_Y), weak_left)
    assert not in_exploited_flank(Point(FINAL_X, LOW_Y), weak_left)
    assert not in_exploited_final_third(Point(FINAL_X, 34.0), _style(Channel.CENTRE))


def test_every_club_has_a_wide_weak_flank() -> None:
    assert all(p.style.weak_flank in (Channel.LEFT, Channel.RIGHT) for p in CLUB_PRESETS.values())


@pytest.mark.parametrize(("home", "away"), [("kestrel_bay", "ironvale")])
def test_flank_flags_point_at_the_configured_weak_flank(home: str, away: str) -> None:
    hits = total = 0
    for seed in PRECISION_SEEDS:
        metadata = build_fixture(home, away, seed)
        analyzer = MatchAnalyzer(metadata)
        for event in simulate_match(metadata).events:
            analyzer.ingest(event)
        defending = {metadata.home.team_id: metadata.away.style, metadata.away.team_id: metadata.home.style}
        for moment in analyzer.moments:
            facts = moment.facts
            if (moment.kind is MomentKind.TACTICAL_PATTERN and facts["pattern"] in FLANK_PATTERNS
                    and facts["channel"] != Channel.CENTRE.value and moment.team_id is not None):
                total += 1
                hits += facts["channel"] == exploited_channel(defending[moment.team_id]).value
    assert total and hits / total >= MIN_PRECISION
