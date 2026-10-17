"""Pure fitting of persona card body text (a prefix plus an explanation) into the persona's word budget.

The budget is the persona's max_words times the validator's WORD_BUDGET_TOLERANCE, so a fitted body always passes
the card validator's length check. Text is trimmed to its leading whole sentences, and when even the first sentence
does not fit it is cut at a word boundary and marked with TRUNCATION_MARK, so no number or word is ever split.
"""

import re

from insidegame.agents.validation import WORD_BUDGET_TOLERANCE
from insidegame.core.exceptions import CardBudgetError

SENTENCE_END: re.Pattern[str] = re.compile(r"[.!?](?=\s|$)")
TRUNCATION_MARK: str = "..."
TRAILING_PUNCTUATION: str = ",;:"


def word_budget(max_words: int) -> float:
    """The most words a persona card body may hold: the same bound the card validator enforces."""
    return max_words * WORD_BUDGET_TOLERANCE


def _word_count(text: str) -> int:
    return len(text.split())


def _leading_sentences(text: str, room: float) -> str:
    """The longest run of leading whole sentences of text holding at most room words, or an empty string."""
    fitted = ""
    for match in SENTENCE_END.finditer(text):
        candidate = text[:match.end()]
        if _word_count(candidate) > room:
            break
        fitted = candidate
    return fitted


def _truncated(text: str, room: float) -> str:
    """The first int(room) whole words of text, ending in TRUNCATION_MARK."""
    words = text.split()[:int(room)]
    if not words:
        return ""
    return " ".join(words).rstrip(TRAILING_PUNCTUATION) + TRUNCATION_MARK


def fit_card_body(prefix: str, text: str, max_words: int) -> str:
    """Return prefix + text when it fits the budget, else prefix + the leading whole sentences that fit.

    When not even the first sentence fits, the first sentence is cut at a word boundary (no partial words) and
    marked with TRUNCATION_MARK. The prefix is always kept unchanged; an empty prefix is allowed.
    Raises CardBudgetError when the prefix alone exceeds the budget, since no body could then fit.
    """
    budget = word_budget(max_words)
    if _word_count(prefix + text) <= budget:
        return prefix + text
    room = budget - _word_count(prefix)
    if room < 0:
        raise CardBudgetError(f"The card prefix {prefix!r} alone exceeds the {max_words}-word budget")
    sentences = _leading_sentences(text, room)
    return prefix + (sentences or _truncated(text, room))
