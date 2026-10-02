"""Pass quality model producing an explainable 0-100 difficulty rating per pass.

The rating is a weighted sum of length, pressure, forward progression, final-third target, and switch of play.
Each component is returned alongside the rating so downstream agents can explain why a pass was hard.
"""

from dataclasses import asdict, dataclass

from insidegame.core.constants import PITCH_LENGTH_M
from insidegame.core.geometry import Point, distance

FINAL_THIRD_START_M: float = PITCH_LENGTH_M * 2 / 3
LENGTH_SCALE_M: float = 50.0
PROGRESSION_SCALE_M: float = 30.0
SWITCH_OF_PLAY_M: float = 25.0
PROGRESSIVE_PASS_M: float = 10.0
RATING_SCALE: float = 100.0
RATING_DECIMALS: int = 1

WEIGHT_LENGTH: float = 0.35
WEIGHT_PRESSURE: float = 0.20
WEIGHT_PROGRESSION: float = 0.20
WEIGHT_FINAL_THIRD: float = 0.15
WEIGHT_SWITCH: float = 0.10


@dataclass(frozen=True)
class PassQuality:
    """Difficulty rating with its normalised contributing factors."""

    difficulty: float
    length_m: float
    length_factor: float
    pressure_factor: float
    progression_factor: float
    final_third_factor: float
    switch_factor: float
    progressive: bool
    final_third_entry: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return asdict(self)


def _unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def assess_pass(start: Point, end: Point, under_pressure: bool) -> PassQuality:
    """Rate a pass from start to end in the passer's attacking frame."""
    length = distance(start, end)
    forward = end.x - start.x
    factors = {
        "length_factor": _unit(length / LENGTH_SCALE_M),
        "pressure_factor": 1.0 if under_pressure else 0.0,
        "progression_factor": _unit(forward / PROGRESSION_SCALE_M),
        "final_third_factor": 1.0 if end.x >= FINAL_THIRD_START_M else 0.0,
        "switch_factor": 1.0 if abs(end.y - start.y) >= SWITCH_OF_PLAY_M else 0.0,
    }
    weighted = (
        WEIGHT_LENGTH * factors["length_factor"]
        + WEIGHT_PRESSURE * factors["pressure_factor"]
        + WEIGHT_PROGRESSION * factors["progression_factor"]
        + WEIGHT_FINAL_THIRD * factors["final_third_factor"]
        + WEIGHT_SWITCH * factors["switch_factor"]
    )
    return PassQuality(
        difficulty=round(RATING_SCALE * weighted, RATING_DECIMALS),
        length_m=round(length, RATING_DECIMALS),
        progressive=forward >= PROGRESSIVE_PASS_M,
        final_third_entry=start.x < FINAL_THIRD_START_M <= end.x,
        **factors,
    )
