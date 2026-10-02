"""Pure replay pacing: how long to wait before emitting the next event at a given speed.

Speed is match seconds per wall-clock second, so 10 replays a 90-minute match in about 9 minutes.
The half-time break is compressed to a fixed number of match seconds.
"""

from insidegame.domain.events import MatchEvent

DEFAULT_SPEED: float = 10.0
MIN_SPEED: float = 1.0
MAX_SPEED: float = 600.0
HALF_TIME_BREAK_MATCH_S: float = 60.0


def replay_delay_s(previous: MatchEvent | None, event: MatchEvent, speed: float) -> float:
    """Wall-clock seconds to wait between previous and event at the given speed."""
    if previous is None:
        return 0.0
    if event.period != previous.period:
        return HALF_TIME_BREAK_MATCH_S / speed
    return max(0.0, event.match_second - previous.match_second) / speed
