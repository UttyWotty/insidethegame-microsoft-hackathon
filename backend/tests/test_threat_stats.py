"""Tests for expected threat (xT) attribution in running statistics, the snapshot, and the analysis update.

A full simulated match is analysed with live tracking positions, and team and player totals are reconciled with
the per-event threat. A second run without positions checks that xT is still credited while line counters stay 0.
"""

import pytest
from threat_helpers import TrackedMatch, analyse_with_tracking

from insidegame.analytics.analyzer import THREAT_LEADERS_IN_SNAPSHOT, MatchAnalyzer
from insidegame.domain.enums import EventType, Outcome

TOLERANCE = 1e-9
THREAT_KEYS = {"event_id", "team_id", "player_id", "action", "xt_start", "xt_end", "xt_added", "opponents_bypassed",
               "lines_broken", "breaks_line"}
COUNTER_KEYS = {"xt_added", "line_breaking_passes", "opponents_bypassed"}


@pytest.fixture(scope="module")
def tracked() -> TrackedMatch:
    return analyse_with_tracking("kestrel_bay", "ironvale", 7)


def test_team_xt_equals_the_sum_over_its_completed_passes_and_carries(tracked: TrackedMatch) -> None:
    for team in (tracked.result.metadata.home, tracked.result.metadata.away):
        threats = [u.threat for u in tracked.updates if u.threat and u.threat.team_id == team.team_id]
        assert threats and all(t.action in (EventType.PASS, EventType.CARRY) for t in threats)
        stats = tracked.analyzer.stats.teams[team.team_id]
        assert abs(stats.xt_added - sum(t.xt_added for t in threats)) < TOLERANCE
        assert stats.line_breaking_passes == sum(t.breaks_line for t in threats)
        assert stats.opponents_bypassed == sum(t.line_break.opponents_bypassed for t in threats if t.line_break)
        assert stats.line_breaking_passes > 0


def test_player_totals_sum_to_their_team(tracked: TrackedMatch) -> None:
    for team_id, team in tracked.analyzer.stats.teams.items():
        players = [p for p in tracked.analyzer.stats.players.values() if p.team_id == team_id]
        assert abs(sum(p.xt_added for p in players) - team.xt_added) < TOLERANCE
        assert sum(p.line_breaking_passes for p in players) == team.line_breaking_passes
        assert sum(p.opponents_bypassed for p in players) == team.opponents_bypassed


def test_only_completed_passes_and_carries_are_credited(tracked: TrackedMatch) -> None:
    for update in tracked.updates:
        event = update.event
        credited = event.event_type in (EventType.PASS, EventType.CARRY) and event.outcome is Outcome.SUCCESS
        assert (update.threat is not None) == (credited and event.start is not None and event.end is not None)
        if update.threat is not None and event.event_type is EventType.CARRY:
            assert update.threat.line_break is None


def test_ingest_without_positions_credits_xt_but_no_line_breaks(tracked: TrackedMatch) -> None:
    analyzer = MatchAnalyzer(tracked.result.metadata)
    for event in tracked.result.events:
        analyzer.ingest(event)
    for team_id, team in analyzer.stats.teams.items():
        assert abs(team.xt_added - tracked.analyzer.stats.teams[team_id].xt_added) < TOLERANCE
        assert team.line_breaking_passes == 0 and team.opponents_bypassed == 0


def test_snapshot_threat_leaders_are_positive_sorted_and_capped(tracked: TrackedMatch) -> None:
    snapshot = tracked.analyzer.snapshot()
    leaders = snapshot["threat_leaders"]
    assert isinstance(leaders, list) and 0 < len(leaders) <= THREAT_LEADERS_IN_SNAPSHOT
    assert all(leader["xt_added"] > 0 for leader in leaders)
    keys = [(-leader["xt_added"], -leader["line_breaking_passes"], leader["name"]) for leader in leaders]
    assert keys == sorted(keys)
    best = max(tracked.analyzer.stats.players.values(), key=lambda p: p.xt_added)
    assert leaders[0]["player_id"] == best.player_id
    home_stats = snapshot["home"]["stats"]  # type: ignore[index]
    assert COUNTER_KEYS <= set(home_stats)


def test_update_threat_has_exactly_the_documented_keys(tracked: TrackedMatch) -> None:
    with_threat = next(u for u in tracked.updates if u.threat is not None and u.threat.line_break is not None)
    data = with_threat.to_dict()["threat"]
    assert isinstance(data, dict) and set(data) == THREAT_KEYS
    assert data["action"] == "pass" and isinstance(data["opponents_bypassed"], int)
    assert data["xt_added"] == round(with_threat.threat.xt_added, 3)  # type: ignore[union-attr]
    without = next(u for u in tracked.updates if u.event.event_type is EventType.SHOT)
    assert without.to_dict()["threat"] is None


def test_counter_dict_rounds_xt_to_three_decimals(tracked: TrackedMatch) -> None:
    team = next(iter(tracked.analyzer.stats.teams.values()))
    data = team.to_dict()
    assert data["xt_added"] == round(team.xt_added, 3)
    assert data["line_breaking_passes"] == team.line_breaking_passes
