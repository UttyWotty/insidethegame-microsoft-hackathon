"""Minimal last-resort outputs for the degraded broadcast path when a template itself raises.

Each builder uses only the moment's kind and broadcast minute label, plus fixed documented text, so it cannot fail on
bad facts and always passes the explanation, commentary, and card validators. These are pure functions with no I/O.
"""

from insidegame.agents.card_text import fit_card_body
from insidegame.agents.context import MomentContext
from insidegame.agents.schemas import Commentary, Explanation, PersonaCard, TacticalTheme

TEMPLATE_FAILED_NOTE: str = "template failed"
NO_PREFIX: str = ""
MINIMAL_WHY_IT_MATTERS: str = "This is a key moment in the match. Full analysis is unavailable for it right now."
MINIMAL_THEME: TacticalTheme = TacticalTheme.CONTROL
KIND_SEPARATOR: str = "_"
WORD_SEPARATOR: str = " "


def kind_title(context: MomentContext) -> str:
    """Return the moment kind as a readable title, for example "Big chance missed"."""
    return context.moment.kind.value.replace(KIND_SEPARATOR, WORD_SEPARATOR).capitalize()


def minimal_explanation(context: MomentContext) -> Explanation:
    """Build an explanation from the minute label and kind title only.

    The headline is "<minute label> <kind title>"; why_it_matters is MINIMAL_WHY_IT_MATTERS, evidence is empty, and
    the theme is MINIMAL_THEME (a neutral fixed choice, since no facts are trusted). The only numbers come from the
    minute label, which is part of the prompt evidence, so the explanation validator accepts it.
    """
    headline = f"{context.moment.minute_label}{WORD_SEPARATOR}{kind_title(context)}"
    return Explanation(headline=headline, why_it_matters=MINIMAL_WHY_IT_MATTERS, evidence=[], theme=MINIMAL_THEME)


def minimal_commentary(explanation: Explanation) -> Commentary:
    """Use the explanation headline as the commentary line."""
    return Commentary(line=explanation.headline)


def minimal_card(explanation: Explanation, max_words: int) -> PersonaCard:
    """Build a card titled with the explanation headline, with no stat callouts and the headline as its body.

    The body is fitted to max_words (the persona's budget) with an empty prefix, which cannot raise, so the card
    validator's length check always passes; its numbers come only from the explanation, which is card evidence.
    """
    body = fit_card_body(NO_PREFIX, explanation.headline, max_words)
    return PersonaCard(title=explanation.headline, body=body, stat_callouts=[])
