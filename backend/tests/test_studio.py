"""Tests for the studio analysis visuals.

They check grid density scaling and frame conversion, pass network links, space control shares, and that the
analyst's theme picks the visual. All logic is pure.
"""

from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent
from insidegame.studio.control import CONTROL_COLS, space_control
from insidegame.studio.maps import GRID_COLS, MIN_LINK_PASSES, ON_BALL, density, pass_network
from insidegame.studio.themes import DEFAULT_VISUAL, StudioVisual, visual_for


def _event(seq: int, team: str, kind: EventType, start: Point, player: str = "h1", receiver: str | None = None,
           outcome: Outcome | None = Outcome.SUCCESS) -> MatchEvent:
    return MatchEvent(f"e{seq}", "m", seq, 1, float(seq), kind, team, player, 1, start, 0, 0,
                      outcome=outcome, receiver_id=receiver)


def test_density_scales_to_the_busiest_cell_and_mirrors_the_away_side() -> None:
    events = [_event(1, "home", EventType.PASS, Point(1.0, 1.0)), _event(2, "home", EventType.PASS, Point(1.0, 1.0)),
              _event(3, "home", EventType.CARRY, Point(104.0, 67.0)), _event(4, "away", EventType.PASS, Point(1.0, 1.0))]
    home = density(events, "home", "home", ON_BALL)
    assert home[0][0] == 1.0 and home[-1][GRID_COLS - 1] == 0.5
    away = density(events, "away", "home", ON_BALL)
    assert away[-1][GRID_COLS - 1] == 1.0 and away[0][0] == 0.0


def test_pass_network_links_only_frequent_combinations() -> None:
    events = [_event(i, "home", EventType.PASS, Point(30.0, 20.0), "h1", "h2") for i in range(MIN_LINK_PASSES)]
    events += [_event(10, "home", EventType.PASS, Point(50.0, 40.0), "h2", "h3"),
               _event(11, "home", EventType.PASS, Point(50.0, 40.0), "h3", "h1", Outcome.FAILURE)]
    network = pass_network(events, "home", "home")
    assert network.links == [("h1", "h2", MIN_LINK_PASSES)]
    assert {n.player_id: n.passes for n in network.nodes} == {"h1": MIN_LINK_PASSES, "h2": 1}


def test_space_control_gives_each_cell_to_the_nearest_team() -> None:
    control = space_control([("h1", 20.0, 34.0), ("a1", 85.0, 34.0)], frozenset({"h1"}))
    assert control.home_share == 52.4 and control.home_thirds == (100.0, 57.1, 0.0)
    assert control.owners[0][0] == 1 and control.owners[0][CONTROL_COLS - 1] == -1


def test_the_analyst_theme_picks_the_visual() -> None:
    assert visual_for("pressure_shift") is StudioVisual.PRESSING
    assert visual_for("control") is StudioVisual.PASS_NETWORK
    assert visual_for(None) is DEFAULT_VISUAL and visual_for("unknown") is DEFAULT_VISUAL
