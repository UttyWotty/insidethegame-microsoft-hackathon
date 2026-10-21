"""Validators that accept or reject each agent's structured output.

Validators enforce numeric grounding against evidence, persona word budgets, and translation integrity.
Each returns None when the output is acceptable, or a short reason the agent can use to correct itself.
"""

from collections.abc import Callable

from insidegame.agents.grounding import check_grounding, extract_numbers
from insidegame.agents.schemas import (
    Commentary,
    CompanionAnswer,
    Explanation,
    MatchRecap,
    PersonaCard,
    RecapTake,
    TranslatedCard,
    TranslatedLine,
)

WORD_BUDGET_TOLERANCE: float = 1.3
COMMENTARY_MAX_WORDS: int = 30
ANSWER_MAX_WORDS: int = 80


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
    """Validator for translations: a real title (not the schema name), the same numbers, and one label per callout."""
    def validate(value: TranslatedCard) -> str | None:
        if value.card_title.strip() in {"", TranslatedCard.__name__}:
            return "card_title must be the input card_title translated into the target language"
        if len(value.stat_labels) != len(source.stat_callouts):
            return f"provide exactly {len(source.stat_callouts)} stat labels"
        expected = sorted(extract_numbers(f"{source.title} {source.body}"))
        if sorted(extract_numbers(f"{value.card_title} {value.body}")) != expected:
            return "numbers must be identical to the source text"
        return None
    return validate


def recap_validator(evidence: dict[str, object], allowed_names: set[str]) -> Callable[[MatchRecap], str | None]:
    """Validator for recaps: grounded, and the standout player must be a real player."""
    def validate(value: MatchRecap) -> str | None:
        if value.standout_player not in allowed_names:
            return "standout_player must be a player named in the input"
        texts = [value.headline, value.summary, value.tactical_story, *value.turning_points]
        return _grounding_problem(texts, lambda: evidence)
    return validate


def answer_validator(evidence: Callable[[], object]) -> Callable[[CompanionAnswer], str | None]:
    """Validator for companion answers: concise and grounded in the match context or tool results."""
    def validate(value: CompanionAnswer) -> str | None:
        if len(value.answer.split()) > ANSWER_MAX_WORDS * WORD_BUDGET_TOLERANCE:
            return f"the answer must be at most {ANSWER_MAX_WORDS} words"
        return _grounding_problem([value.answer, *(c.value for c in value.stat_callouts)], evidence)
    return validate


def take_validator(evidence: Callable[[], object], max_words: int) -> Callable[[RecapTake], str | None]:
    """Validator for persona recap takes: grounded and within the persona's word budget."""
    def validate(value: RecapTake) -> str | None:
        if len(value.take.split()) > max_words * WORD_BUDGET_TOLERANCE:
            return f"the take must be at most {max_words} words"
        return _grounding_problem([value.headline, value.take], evidence)
    return validate


def line_translation_validator(source: str) -> Callable[[TranslatedLine], str | None]:
    """Validator for translated commentary: identical numbers to the source line."""
    def validate(value: TranslatedLine) -> str | None:
        if sorted(extract_numbers(value.line)) != sorted(extract_numbers(source)):
            return "numbers must be identical to the source line"
        return None
    return validate
