"""Pure live win probability from the score, the time left, and how dangerous each team has been.

Each side's goals in the remaining time follow a Poisson distribution whose rate blends a prior (typical
top-flight scoring with home advantage) with the team's own expected-goals rate so far, trusting the live rate more
as the match goes on. Summing the outcomes on top of the current score gives home win, draw, and away win
probabilities that move with goals, pressure, and the clock.
"""

import math
from dataclasses import dataclass

from insidegame.core.constants import PERIOD_SECONDS

MATCH_SECONDS: float = 2.0 * PERIOD_SECONDS
PRIOR_HOME_GOALS: float = 1.55
PRIOR_AWAY_GOALS: float = 1.25
MIN_REMAINING_S: float = 0.0
MAX_GOALS: int = 10
DECIMALS: int = 3


@dataclass(frozen=True)
class WinProbability:
    """Probabilities of a home win, a draw, and an away win; they sum to one."""

    home: float
    draw: float
    away: float

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-friendly representation."""
        return {"home": self.home, "draw": self.draw, "away": self.away}


def _poisson(rate: float) -> list[float]:
    probabilities = [math.exp(-rate) * rate ** k / math.factorial(k) for k in range(MAX_GOALS)]
    probabilities.append(max(1.0 - sum(probabilities), 0.0))
    return probabilities


def _rate(prior_per_match: float, xg: float, elapsed_s: float, remaining_s: float) -> float:
    """Expected goals in the remaining time: the prior rate blended with the observed xG rate by time played."""
    share = elapsed_s / MATCH_SECONDS
    observed = xg / elapsed_s if elapsed_s > 0 else 0.0
    per_second = (1.0 - share) * prior_per_match / MATCH_SECONDS + share * observed
    return per_second * remaining_s


def win_probability(score_home: int, score_away: int, xg_home: float, xg_away: float, elapsed_s: float,
                    finished: bool) -> WinProbability:
    """Home, draw, and away probabilities; a finished match is certain."""
    remaining = 0.0 if finished else max(MATCH_SECONDS - elapsed_s, MIN_REMAINING_S)
    home_goals = _poisson(_rate(PRIOR_HOME_GOALS, xg_home, elapsed_s, remaining))
    away_goals = _poisson(_rate(PRIOR_AWAY_GOALS, xg_away, elapsed_s, remaining))
    home = draw = away = 0.0
    for h, ph in enumerate(home_goals):
        for a, pa in enumerate(away_goals):
            margin = (score_home + h) - (score_away + a)
            p = ph * pa
            if margin > 0:
                home += p
            elif margin < 0:
                away += p
            else:
                draw += p
    total = home + draw + away
    return WinProbability(round(home / total, DECIMALS), round(draw / total, DECIMALS), round(away / total, DECIMALS))
