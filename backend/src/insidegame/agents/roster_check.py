"""Deterministic check that generated text names only players who are actually in the match.

Synthetic player names come from known first-name and surname pools, so any pool-shaped full name that is not in
this match's squads is a hallucinated player. It runs before the model fact-checker and needs no model call.
"""

import re
from collections.abc import Iterable

from insidegame.simulation.roster import FIRST_NAMES, LAST_NAMES

FULL_NAME_PATTERN: re.Pattern[str] = re.compile(r"\b([A-Z][a-z]+) ([A-Z][a-z]+)\b")
FIRST_NAME_POOL: frozenset[str] = frozenset(FIRST_NAMES)
LAST_NAME_POOL: frozenset[str] = frozenset(LAST_NAMES)


def unknown_players(texts: Iterable[str], squad_names: Iterable[str]) -> list[str]:
    """Return player-like full names in texts that are not in the match squads."""
    known = set(squad_names)
    found = []
    for text in texts:
        for first, last in FULL_NAME_PATTERN.findall(text):
            name = f"{first} {last}"
            looks_like_player = first in FIRST_NAME_POOL and last in LAST_NAME_POOL
            if looks_like_player and name not in known and name not in found:
                found.append(name)
    return found
