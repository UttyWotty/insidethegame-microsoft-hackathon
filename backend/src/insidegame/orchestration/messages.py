"""Typed messages passed between workflow executors.

Each message carries the job plus the provenance-rich outcomes produced so far.
Keeping messages immutable makes executor handoffs explicit and easy to test.
"""

from dataclasses import dataclass

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.runner import AgentOutcome
from insidegame.agents.schemas import Commentary, Explanation, PersonaCard, TranslatedCard


@dataclass(frozen=True)
class MomentJob:
    """A key moment selected for broadcast, with the viewers it must reach."""

    context: MomentContext
    viewers: tuple[ViewerContext, ...]


@dataclass(frozen=True)
class ExplainedMoment:
    """Analyst handoff: the job and its explanation."""

    job: MomentJob
    explanation: AgentOutcome[Explanation]


@dataclass(frozen=True)
class NarrationResult:
    """Narrator handoff: the commentary line."""

    commentary: AgentOutcome[Commentary]


@dataclass(frozen=True)
class PersonalizedCard:
    """One viewer's card, translated when the viewer's language is not English.

    Defaults: translation is None when no translation was needed.
    """

    viewer: ViewerContext
    card: AgentOutcome[PersonaCard]
    translation: AgentOutcome[TranslatedCard] | None = None


@dataclass(frozen=True)
class PersonalizationResult:
    """Personalizer handoff: every viewer's card."""

    cards: tuple[PersonalizedCard, ...]

