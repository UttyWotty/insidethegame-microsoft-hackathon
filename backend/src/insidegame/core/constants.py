"""Physical and temporal constants describing a football pitch and match.

All coordinates in the project use metres on a 105 x 68 pitch.
Event coordinates are relative to the acting team, which always attacks toward x = PITCH_LENGTH_M.
"""

PITCH_LENGTH_M: float = 105.0
PITCH_WIDTH_M: float = 68.0
GOAL_WIDTH_M: float = 7.32
GOAL_CENTER_Y_M: float = PITCH_WIDTH_M / 2

SECONDS_PER_MINUTE: int = 60
PERIOD_MINUTES: int = 45
PERIOD_SECONDS: int = PERIOD_MINUTES * SECONDS_PER_MINUTE
PERIODS: tuple[int, ...] = (1, 2)

ATTRIBUTE_MIN: float = 0.0
ATTRIBUTE_MAX: float = 1.0
