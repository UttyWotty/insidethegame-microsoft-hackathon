"""Base 4-3-3 formation slots, in a team's own attacking frame, indexed like the generated roster.

Roster order is goalkeeper, right-back, two centre-backs, left-back, holding midfielder, two central midfielders,
right winger, striker, left winger, matching SHIRT_NUMBERS in the simulation roster.
"""

from insidegame.core.geometry import Point

SLOTS: tuple[Point, ...] = (
    Point(6.0, 34.0),
    Point(32.0, 58.0), Point(26.0, 42.0), Point(26.0, 26.0), Point(32.0, 10.0),
    Point(42.0, 34.0), Point(48.0, 48.0), Point(50.0, 20.0),
    Point(68.0, 58.0), Point(74.0, 34.0), Point(68.0, 10.0),
)
GOALKEEPER_INDEX: int = 0
DEFENDER_INDICES: frozenset[int] = frozenset({1, 2, 3, 4})
FORWARD_INDICES: frozenset[int] = frozenset({8, 9, 10})
