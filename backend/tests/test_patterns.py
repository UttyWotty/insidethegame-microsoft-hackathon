"""Tests for the pure tactical pattern rules, the stateful PatternMiner, and payoff links.

They check every threshold at and just below its constant, cooldowns, the global gap, window expiry, period resets,
and that a goal links to an earlier flag only when team, period, timing, and zone all match.
All inputs are hand-built events, so every case isolates exactly one rule.
"""

import pytest

from insidegame.analytics.pattern_rules import (
    CHANNEL_OVERLOAD_MIN_COUNT,
    FLANK_EXPOSED_MIN_SUCCESSES,
    PATTERN_WINDOW_S,
    TURNOVER_ZONE_MIN_WINS,
    EntrySample,
    PatternKind,
    TacticalPattern,
    WinSample,
    channel_overload,
    flank_exposed,
    turnover_zone,
)
from insidegame.analytics.patterns import (
    PATTERN_GAP_S,
    PATTERN_KEY_COOLDOWN_S,
    PAYOFF_WINDOW_S,
    FlagRecord,
    PatternMiner,
)
from insidegame.analytics.tactical_facts import exposed_defender
from insidegame.core.geometry import Point
from insidegame.core.zones import Channel, Third
from insidegame.domain.enums import EventType, Outcome, Position
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.simulation.roster import build_fixture

HOME, AWAY = "kba", "irv"
LEFT_Y, CENTRE_Y, RIGHT_Y = 10.0, 34.0, 60.0
ENTRY_FROM_X, ENTRY_TO_X = 60.0, 80.0
MIDDLE_X, DEFENSIVE_X = 50.0, 20.0
FLAG_AT_S = 60.0


@pytest.fixture(scope="module")
def metadata() -> MatchMetadata:
    return build_fixture("kestrel_bay", "ironvale", 1)


def _event(second: float, kind: EventType, team: str | None = HOME, possession: int = 1, *,
           start: Point | None = Point(MIDDLE_X, CENTRE_Y), end: Point | None = None,
           outcome: Outcome | None = None, period: int = 1) -> MatchEvent:
    return MatchEvent(event_id=f"e{second}", match_id="m", sequence=int(second), period=period, match_second=second,
                      event_type=kind, team_id=team, player_id=None, possession_id=possession, start=start,
                      score_home=0, score_away=0, end=end, outcome=outcome)


def _entry(second: float, y: float, team: str = HOME, possession: int = 1, success: bool = True,
           period: int = 1) -> MatchEvent:
    return _event(second, EventType.PASS, team, possession, start=Point(ENTRY_FROM_X, y),
                  end=Point(ENTRY_TO_X, y), outcome=Outcome.SUCCESS if success else Outcome.FAILURE, period=period)


def _samples(channel: Channel, successes: int, failures: int = 0, team: str = HOME) -> list[EntrySample]:
    return ([EntrySample(float(i), team, channel, True) for i in range(successes)]
            + [EntrySample(float(i), team, channel, False) for i in range(failures)])


def _wins(third: Third, channel: Channel, count: int, team: str = HOME) -> list[WinSample]:
    return [WinSample(float(i), team, third, channel) for i in range(count)]


def test_channel_overload_fires_at_its_count_and_share_and_not_below() -> None:
    at = _samples(Channel.LEFT, CHANNEL_OVERLOAD_MIN_COUNT) + _samples(Channel.CENTRE, 4)
    found = channel_overload(at, HOME, AWAY)
    assert found is not None and found.kind is PatternKind.CHANNEL_OVERLOAD and found.channel is Channel.LEFT
    assert (found.count, found.total, found.third) == (7, 11, Third.FINAL)
    too_few = _samples(Channel.LEFT, CHANNEL_OVERLOAD_MIN_COUNT - 1) + _samples(Channel.CENTRE, 2)
    assert channel_overload(too_few, HOME, AWAY) is None
    low_share = _samples(Channel.LEFT, CHANNEL_OVERLOAD_MIN_COUNT) + _samples(Channel.CENTRE, 5)
    assert channel_overload(low_share, HOME, AWAY) is None
    assert channel_overload(at, AWAY, HOME) is None


def test_flank_exposed_fires_at_its_successes_and_rate_and_not_below() -> None:
    found = flank_exposed(_samples(Channel.RIGHT, FLANK_EXPOSED_MIN_SUCCESSES, failures=1), HOME, AWAY)
    assert found is not None and found.kind is PatternKind.FLANK_EXPOSED and found.channel is Channel.RIGHT
    assert (found.count, found.total) == (6, 7)
    assert flank_exposed(_samples(Channel.RIGHT, FLANK_EXPOSED_MIN_SUCCESSES - 1), HOME, AWAY) is None
    assert flank_exposed(_samples(Channel.RIGHT, FLANK_EXPOSED_MIN_SUCCESSES, failures=2), HOME, AWAY) is None


def test_flank_exposed_ignores_the_centre() -> None:
    assert flank_exposed(_samples(Channel.CENTRE, 10), HOME, AWAY) is None


def test_turnover_zone_fires_at_its_count_and_excludes_the_defensive_third() -> None:
    found = turnover_zone(_wins(Third.MIDDLE, Channel.LEFT, TURNOVER_ZONE_MIN_WINS), HOME, AWAY)
    assert found is not None and (found.third, found.channel, found.count) == (Third.MIDDLE, Channel.LEFT, 5)
    assert turnover_zone(_wins(Third.MIDDLE, Channel.LEFT, TURNOVER_ZONE_MIN_WINS - 1), HOME, AWAY) is None
    assert turnover_zone(_wins(Third.DEFENSIVE, Channel.LEFT, 10), HOME, AWAY) is None


def test_share_is_zero_without_samples() -> None:
    pattern = TacticalPattern(PatternKind.CHANNEL_OVERLOAD, HOME, AWAY, Channel.LEFT, Third.FINAL, 0, 0,
                              PATTERN_WINDOW_S)
    assert pattern.share == 0.0
    assert pattern.key == (PatternKind.CHANNEL_OVERLOAD, HOME, Channel.LEFT, Third.FINAL)


def test_flank_exposure_names_the_defending_full_back(metadata: MatchMetadata) -> None:
    defenders = metadata.away.players_in(Position.DEFENDER)
    attack_left = TacticalPattern(PatternKind.FLANK_EXPOSED, HOME, AWAY, Channel.LEFT, Third.FINAL, 6, 6,
                                  PATTERN_WINDOW_S)
    attack_right = TacticalPattern(PatternKind.FLANK_EXPOSED, HOME, AWAY, Channel.RIGHT, Third.FINAL, 6, 6,
                                   PATTERN_WINDOW_S)
    assert exposed_defender(attack_left, metadata) == defenders[0]  # the attacker's left faces the right-back
    assert exposed_defender(attack_right, metadata) == defenders[3]
    overload = TacticalPattern(PatternKind.CHANNEL_OVERLOAD, HOME, AWAY, Channel.LEFT, Third.FINAL, 7, 7,
                               PATTERN_WINDOW_S)
    assert exposed_defender(overload, metadata) is None


def test_miner_flags_once_then_applies_gap_and_key_cooldown(metadata: MatchMetadata) -> None:
    miner = PatternMiner(metadata)
    found = [miner.observe(_entry(float(10 * i), LEFT_Y)) for i in range(1, 8)]
    assert [p.kind if p else None for p in found] == [None] * 5 + [PatternKind.FLANK_EXPOSED, None]
    first_flag_s = 60.0
    assert miner.observe(_entry(first_flag_s + PATTERN_GAP_S - 1, LEFT_Y)) is None
    after_gap = miner.observe(_entry(first_flag_s + PATTERN_GAP_S, LEFT_Y))
    assert PATTERN_GAP_S < PATTERN_KEY_COOLDOWN_S
    assert after_gap is not None and after_gap.kind is PatternKind.CHANNEL_OVERLOAD  # flank key still cooling down


def test_samples_expire_after_the_window(metadata: MatchMetadata) -> None:
    miner = PatternMiner(metadata)
    for i in range(FLANK_EXPOSED_MIN_SUCCESSES - 1):
        assert miner.observe(_entry(float(i), LEFT_Y)) is None
    assert miner.observe(_entry(PATTERN_WINDOW_S + 10.0, LEFT_Y)) is None
    assert len(miner.entries) == 1


def test_period_start_resets_windows_and_possessions(metadata: MatchMetadata) -> None:
    miner = PatternMiner(metadata)
    for i in range(FLANK_EXPOSED_MIN_SUCCESSES - 1):
        miner.observe(_entry(float(i), LEFT_Y))
    miner.observe(_event(2700.0, EventType.PERIOD_START, None, start=None, period=2))
    assert not miner.entries and not miner.wins and not miner.possessions
    assert miner.observe(_entry(2701.0, LEFT_Y, period=2)) is None


def test_events_without_team_or_start_and_an_empty_stream_produce_nothing(metadata: MatchMetadata) -> None:
    miner = PatternMiner(metadata)
    assert miner.observe(_event(1.0, EventType.PERIOD_END, None, start=None)) is None
    assert miner.observe(_event(2.0, EventType.PASS, HOME, start=None)) is None
    assert miner.observe(_event(3.0, EventType.PASS, None)) is None
    assert not miner.entries and not miner.flags and miner.payoff(_event(4.0, EventType.GOAL)) is None


def _flagged_miner(metadata: MatchMetadata, kind: PatternKind = PatternKind.FLANK_EXPOSED,
                   channel: Channel = Channel.LEFT, third: Third = Third.FINAL) -> PatternMiner:
    miner = PatternMiner(metadata)
    pattern = TacticalPattern(kind, HOME, AWAY, channel, third, 6, 6, PATTERN_WINDOW_S)
    miner.record_flag(FlagRecord(pattern, "m-flag", 1, FLAG_AT_S, "2'", "summary"))
    return miner


def _attack(miner: PatternMiner, start_s: float, entry_y: float, team: str = HOME,
            possession: int = 2, period: int = 1) -> MatchEvent:
    miner.observe(_event(start_s, EventType.POSSESSION_CHANGE, team, possession, period=period))
    miner.observe(_entry(start_s + 2, entry_y, team, possession, period=period))
    goal = _event(start_s + 4, EventType.GOAL, team, possession, start=Point(95.0, entry_y), period=period)
    miner.observe(goal)
    return goal


def test_payoff_links_a_matching_goal_to_the_earlier_flag(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    link = miner.payoff(_attack(miner, 100.0, LEFT_Y))
    assert link is not None and link.flag.moment_id == "m-flag"
    assert link.facts() == {"flagged_minute": "2'", "flagged_moment_id": "m-flag",
                            "flagged_pattern": "flank_exposed", "flagged_summary": "summary"}


def test_payoff_rejects_another_team(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    assert miner.payoff(_attack(miner, 100.0, LEFT_Y, team=AWAY)) is None


def test_payoff_rejects_another_period(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    miner.observe(_event(2700.0, EventType.PERIOD_START, None, start=None, period=2))
    assert miner.payoff(_attack(miner, 2710.0, LEFT_Y, period=2)) is None


def test_payoff_rejects_a_possession_that_began_before_the_flag(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    assert miner.payoff(_attack(miner, FLAG_AT_S - 10.0, LEFT_Y)) is None


def test_payoff_rejects_goals_outside_the_window(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    assert miner.payoff(_attack(miner, FLAG_AT_S + PAYOFF_WINDOW_S, LEFT_Y)) is None


def test_payoff_rejects_another_channel(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata)
    assert miner.payoff(_attack(miner, 100.0, RIGHT_Y)) is None


def test_turnover_zone_payoff_needs_a_win_in_the_flagged_zone(metadata: MatchMetadata) -> None:
    miner = _flagged_miner(metadata, PatternKind.TURNOVER_ZONE, Channel.CENTRE, Third.MIDDLE)
    assert miner.payoff(_attack(miner, 100.0, LEFT_Y)) is not None  # the win at (50, 34) is middle third, centre
    miner.observe(_event(200.0, EventType.POSSESSION_CHANGE, HOME, 3, start=Point(DEFENSIVE_X, CENTRE_Y)))
    goal = _event(204.0, EventType.GOAL, HOME, 3, start=Point(95.0, CENTRE_Y))
    assert miner.payoff(goal) is None
