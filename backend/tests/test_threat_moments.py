"""Tests for threat_created key moments and the expected threat (xT) facts on existing pass moments.

They check the rule (pass, line break, xT threshold, cooldown per period), the exact facts, the service wiring that
feeds tracking positions, and the rate over thirty simulated matches, which must stay selective but visible.
Matches are analysed with the same tracked positions the live pipeline uses, so no mocks are needed.
"""

import statistics

import pytest
from threat_helpers import TrackedMatch, analyse_with_tracking

from insidegame.agents.runner import RunPolicy
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.line_breaks import DefensiveLine, LineBreak
from insidegame.analytics.moments import MomentKind, moment_intensity
from insidegame.analytics.threat import ThreatAction
from insidegame.analytics.threat_moments import (
    THREAT_IMPORTANCE,
    THREAT_MOMENT_COOLDOWN_S,
    THREAT_MOMENT_MIN_XT,
    ThreatMomentRule,
    pass_threat_facts,
    threat_facts,
)
from insidegame.domain.enums import EventType, Intensity, Outcome
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from test_live import _offline_suite

THREAT_FACT_KEYS = {"passer", "receiver", "xt_added", "xt_start", "xt_end", "opponents_bypassed", "lines_broken",
                    "length_m"}
RATE_SEEDS = range(1, 31)
MIN_RATE, MAX_RATE = 1.5, 5.0
OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
BOTH_LINES = (DefensiveLine.MIDFIELD, DefensiveLine.DEFENCE)


def _threat(added: float = 0.04, lines: tuple[DefensiveLine, ...] = BOTH_LINES, action: EventType = EventType.PASS,
            positions: bool = True) -> ThreatAction:
    line_break = LineBreak(5, lines) if positions else None
    return ThreatAction("e", "home", "p1", "p2", action, 0.01, 0.01 + added, line_break)


@pytest.fixture(scope="module")
def tracked() -> TrackedMatch:
    return analyse_with_tracking("kestrel_bay", "ironvale", 7)


def test_rule_needs_a_line_breaking_pass_with_enough_xt() -> None:
    assert ThreatMomentRule().qualifies(_threat(), 1, 100.0)
    assert not ThreatMomentRule().qualifies(_threat(added=THREAT_MOMENT_MIN_XT / 2), 1, 100.0)
    assert not ThreatMomentRule().qualifies(_threat(lines=()), 1, 100.0)
    assert not ThreatMomentRule().qualifies(_threat(action=EventType.CARRY), 1, 100.0)
    assert not ThreatMomentRule().qualifies(_threat(positions=False), 1, 100.0)


def test_rule_cools_down_within_a_period_only() -> None:
    rule = ThreatMomentRule()
    assert rule.qualifies(_threat(), 1, 100.0)
    assert not rule.qualifies(_threat(), 1, 100.0 + THREAT_MOMENT_COOLDOWN_S - 1)
    assert rule.qualifies(_threat(), 1, 100.0 + THREAT_MOMENT_COOLDOWN_S)
    assert rule.qualifies(_threat(), 2, 2700.0 + 101.0)
    assert rule.last == (2, 2801.0)


def test_threat_facts_are_exactly_the_documented_keys() -> None:
    facts = threat_facts(_threat(), "A", "B", 31.4)
    assert set(facts) == THREAT_FACT_KEYS
    assert facts["lines_broken"] == "midfield and defence" and facts["opponents_bypassed"] == 5
    assert threat_facts(_threat(lines=(DefensiveLine.DEFENCE,)), "A", "B", None)["lines_broken"] == "defence"
    assert pass_threat_facts(None) == {} and set(pass_threat_facts(_threat(positions=False))) == {"xt_added"}


def test_threat_moments_in_a_tracked_match_are_well_formed(tracked: TrackedMatch) -> None:
    moments = [m for m in tracked.analyzer.moments if m.kind is MomentKind.THREAT_CREATED]
    assert moments and moment_intensity(MomentKind.THREAT_CREATED) is Intensity.RAISED
    by_event = {u.event.event_id: u for u in tracked.updates}
    for moment in moments:
        assert set(moment.facts) == THREAT_FACT_KEYS and moment.importance == THREAT_IMPORTANCE
        update = by_event[moment.event_ids[0]]
        threat = update.threat
        assert threat is not None and threat.breaks_line and threat.xt_added >= THREAT_MOMENT_MIN_XT
        assert update.event.event_type is EventType.PASS and update.event.outcome is Outcome.SUCCESS
        assert moment.team_id == threat.team_id and moment.player_ids == (threat.player_id, threat.receiver_id)
    for earlier, later in zip(moments, moments[1:]):
        assert earlier.period != later.period or later.match_second - earlier.match_second >= THREAT_MOMENT_COOLDOWN_S


def test_no_threat_moments_without_positions(tracked: TrackedMatch) -> None:
    analyzer = MatchAnalyzer(tracked.result.metadata)
    for event in tracked.result.events:
        analyzer.ingest(event)
    assert not [m for m in analyzer.moments if m.kind is MomentKind.THREAT_CREATED]


def test_difficult_and_long_pass_moments_carry_xt(tracked: TrackedMatch) -> None:
    passes = [m for m in tracked.analyzer.moments if m.kind is MomentKind.DIFFICULT_PASS
              or (m.kind is MomentKind.DISTANCE_THRESHOLD and m.facts.get("indicator") == "long_pass")]
    assert passes
    assert all(isinstance(m.facts["xt_added"], float) and isinstance(m.facts["opponents_bypassed"], int)
               for m in passes)


def test_service_interpret_feeds_tracking_positions_to_line_breaks() -> None:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 3))
    service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, ())
    kicked_off, checked = False, 0
    for event in result.events:
        update = service.interpret(event).update
        if event.event_type is EventType.KICK_OFF:
            kicked_off = True
        elif kicked_off and event.event_type is EventType.PASS and event.outcome is Outcome.SUCCESS:
            assert update.threat is not None and update.threat.line_break is not None
            checked += 1
    assert checked > 0
    assert service.analyzer.stats.teams[result.metadata.home.team_id].opponents_bypassed > 0


def test_threat_moment_rate_over_thirty_matches_is_selective() -> None:
    counts = [sum(m.kind is MomentKind.THREAT_CREATED for m in
                  analyse_with_tracking("kestrel_bay", "ironvale", seed).analyzer.moments) for seed in RATE_SEEDS]
    assert MIN_RATE <= statistics.mean(counts) <= MAX_RATE
