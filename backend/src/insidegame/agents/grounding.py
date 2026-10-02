"""Numeric grounding check that rejects agent text citing numbers absent from the evidence.

Every number in generated text must match a number in the moment context or the agent's tool results.
Matching tolerates normal rounding and ratio-to-percentage conversion so faithful phrasing is not penalised.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

NUMBER_PATTERN: re.Pattern[str] = re.compile(r"\d+(?:\.\d+)?")
ALWAYS_ALLOWED: frozenset[float] = frozenset({0.0, 1.0, 2.0, 3.0})
INTEGER_TOLERANCE: float = 0.5
DECIMAL_TOLERANCE: float = 0.051
PERCENT_FACTOR: float = 100.0
RATIO_UPPER_BOUND: float = 1.0


@dataclass(frozen=True)
class GroundingReport:
    """Result of a grounding check."""

    grounded: bool
    ungrounded: tuple[float, ...]


def extract_numbers(text: str) -> list[float]:
    """Return every non-negative number written in text."""
    return [float(match) for match in NUMBER_PATTERN.findall(text)]


def collect_evidence_numbers(evidence: object) -> set[float]:
    """Walk nested evidence and collect every number, including numbers inside strings."""
    found: set[float] = set()
    stack: list[object] = [evidence]
    while stack:
        item = stack.pop()
        if isinstance(item, bool) or item is None:
            continue
        if isinstance(item, (int, float)):
            found.add(abs(float(item)))
        elif isinstance(item, str):
            found.update(extract_numbers(item))
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set)):
            stack.extend(item)
    return found


def _expand(values: set[float]) -> set[float]:
    expanded = set(values) | ALWAYS_ALLOWED
    expanded.update(v * PERCENT_FACTOR for v in values if v <= RATIO_UPPER_BOUND)
    return expanded


def _matches(number: float, allowed: set[float]) -> bool:
    tolerance = INTEGER_TOLERANCE if number.is_integer() else DECIMAL_TOLERANCE
    return any(abs(number - candidate) <= tolerance for candidate in allowed)


def check_grounding(texts: Iterable[str], evidence: object) -> GroundingReport:
    """Verify that every number in texts is supported by the evidence."""
    allowed = _expand(collect_evidence_numbers(evidence))
    ungrounded = tuple(n for text in texts for n in extract_numbers(text) if not _matches(n, allowed))
    return GroundingReport(grounded=not ungrounded, ungrounded=ungrounded)
