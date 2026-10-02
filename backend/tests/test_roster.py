"""Tests for fictional fixture and squad generation.

They confirm determinism, squad shape, unique identities, and validation errors.
No I/O is involved.
"""

import pytest

from insidegame.core.exceptions import FixtureError
from insidegame.domain.enums import Position
from insidegame.simulation.roster import build_fixture

SQUAD_SIZE = 11


def test_fixture_is_deterministic_for_seed() -> None:
    assert build_fixture("brookhaven", "ironvale", 3) == build_fixture("brookhaven", "ironvale", 3)


def test_different_seeds_produce_different_squads() -> None:
    a = build_fixture("brookhaven", "ironvale", 1)
    b = build_fixture("brookhaven", "ironvale", 2)
    assert a.home.players != b.home.players


def test_squads_have_four_three_three_shape() -> None:
    fixture = build_fixture("kestrel_bay", "silverlake", 0)
    for team in (fixture.home, fixture.away):
        assert len(team.players) == SQUAD_SIZE
        assert len(team.players_in(Position.GOALKEEPER)) == 1
        assert len(team.players_in(Position.DEFENDER)) == 4
        assert len(team.players_in(Position.MIDFIELDER)) == 3
        assert len(team.players_in(Position.FORWARD)) == 3


def test_player_names_and_ids_are_unique_across_fixture() -> None:
    fixture = build_fixture("kestrel_bay", "silverlake", 0)
    players = fixture.home.players + fixture.away.players
    assert len({p.name for p in players}) == len(players)
    assert len({p.player_id for p in players}) == len(players)


def test_unknown_club_raises() -> None:
    with pytest.raises(FixtureError):
        build_fixture("brookhaven", "nowhere", 0)


def test_club_cannot_play_itself() -> None:
    with pytest.raises(FixtureError):
        build_fixture("brookhaven", "brookhaven", 0)
