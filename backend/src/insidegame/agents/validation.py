"""Validators that accept or reject each agent's structured output.

Validators enforce numeric grounding against evidence, persona word budgets, and translation integrity.
Each returns None when the output is acceptable, or a short reason the agent can use to correct itself.
"""

from collections.abc import Callable

from insidegame.agents.grounding import check_grounding, extract_numbers
from insidegame.agents.schemas import Commentary, Explanation, PersonaCard, TranslatedCard

WORD_BUDGET_TOLERANCE: float = 1.3
COMMENTARY_MAX_WORDS: int = 30


def _grounding_problem(texts: list[str], evidence: Callable[[], object]) -> str | None:
    report = check_grounding(texts, evidence())
    if report.grounded:
        return None
    return f"these numbers are not in the input: {', '.join(f'{n:g}' for n in report.ungrounded)}"


def explanation_validator(evidence: Callable[[], object]) -> Callable[[Explanation], str | None]:
    """Validator for analyst explanations; evidence is read lazily so tool results are included."""
    def validate(value: Explanation) -> str | None:
        return _grounding_problem([value.headline, value.why_it_matters, *value.evidence], evidence)
    return validate


def commentary_validator(evidence: Callable[[], object]) -> Callable[[Commentary], str | None]:
    """Validator for narrator lines: grounded and short enough to say live."""
    def validate(value: Commentary) -> str | None:
        if len(value.line.split()) > COMMENTARY_MAX_WORDS * WORD_BUDGET_TOLERANCE:
            return f"the line must be at most {COMMENTARY_MAX_WORDS} words"
        return _grounding_problem([value.line], evidence)
    return validate


def card_validator(evidence: Callable[[], object], max_words: int) -> Callable[[PersonaCard], str | None]:
    """Validator for persona cards: grounded and within the persona's word budget."""
    def validate(value: PersonaCard) -> str | None:
        if len(value.body.split()) > max_words * WORD_BUDGET_TOLERANCE:
            return f"the body must be at most {max_words} words"
        texts = [value.title, value.body, *(c.value for c in value.stat_callouts)]
        return _grounding_problem(texts, evidence)
    return validate


def translation_validator(source: PersonaCard) -> Callable[[TranslatedCard], str | None]:
    """Validator for translations: same numbers as the source and one label per callout."""
    def validate(value: TranslatedCard) -> str | None:
        if len(value.stat_labels) != len(source.stat_callouts):
            return f"provide exactly {len(source.stat_callouts)} stat labels"
        expected = sorted(extract_numbers(f"{source.title} {source.body}"))
        if sorted(extract_numbers(f"{value.title} {value.body}")) != expected:
            return "numbers must be identical to the source text"
        return None
    return validate
