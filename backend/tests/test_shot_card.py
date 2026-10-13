"""Tests for the broadcast shot card.

They check that placements agree with each outcome, that cards are deterministic, and that the seeded match is
unchanged because the simulator's random sequence is not used. All logic is pure.
"""

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.shot_card import GOAL_HEIGHT_M, shot_card
from insidegame.core.constants import GOAL_WIDTH_M
from insidegame.domain.enums import EventType
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

HALF = GOAL_WIDTH_M / 2


def _cards() -> list:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    analyzer = MatchAnalyzer(result.metadata)
    return [u.shot for u in map(analyzer.ingest, result.events) if u.shot is not None]


def test_placements_agree_with_every_outcome() -> None:
    cards = _cards()
    assert {c.result for c in cards} >= {"goal", "saved", "off_target"}
    for card in cards:
        if card.result in ("goal", "saved"):
            assert abs(card.placement_y) < HALF and 0 <= card.placement_z < GOAL_HEIGHT_M
        elif card.result == "off_target":
            assert abs(card.placement_y) > HALF or card.placement_z > GOAL_HEIGHT_M
        else:
            assert card.placement_y is None and card.keeper_y is None
        if card.result == "saved":
            assert card.keeper_y == card.placement_y
        assert 0 < card.distance_m < 60 and 0 < card.angle_deg < 180


def test_cards_are_deterministic_and_leave_the_match_unchanged() -> None:
    assert [c.to_dict() for c in _cards()] == [c.to_dict() for c in _cards()]
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    shots = [e for e in result.events if e.event_type is EventType.SHOT]
    assert shot_card(shots[0], 0.1) == shot_card(shots[0], 0.1)
