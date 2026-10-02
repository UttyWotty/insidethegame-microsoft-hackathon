"""Typed messages passed between workflow executors.

Each message carries the job plus the provenance-rich outcomes produced so far.
Keeping messages immutable makes executor handoffs explicit and easy to test.
"""

from dataclasses import dataclass, field
from enum import StrEnum

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


class Verdict(StrEnum):
    """What the fact-checking stage did with a draft."""

    APPROVED = "approved"
    REVISED = "revised"
    REPLACED = "replaced"
    SKIPPED = "skipped"


class Checker(StrEnum):
    """Who made the fact-check decision."""

    MODEL = "model"
    RULES = "rules"
    NONE = "none"


@dataclass(frozen=True)
class FactCheckRecord:
    """Provenance of the fact-check for one draft.

    Defaults: no issues and zero latency.
    """

    verdict: Verdict
    checker: Checker
    issues: tuple[str, ...] = field(default_factory=tuple)
    latency_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"verdict": self.verdict.value, "checker": self.checker.value, "issues": list(self.issues),
                "latency_ms": self.latency_ms}


SKIPPED_CHECK: FactCheckRecord = FactCheckRecord(Verdict.SKIPPED, Checker.NONE)


@dataclass(frozen=True)
class PersonalizedCard:
    """One viewer's card, its fact-check, and its translation when the viewer's language is not English.

    Defaults: translation is None when not needed; fact_check is SKIPPED_CHECK until the card is checked.
    """

    viewer: ViewerContext
    card: AgentOutcome[PersonaCard]
    translation: AgentOutcome[TranslatedCard] | None = None
    fact_check: FactCheckRecord = SKIPPED_CHECK


@dataclass(frozen=True)
class PersonalizationResult:
    """Personalizer handoff: every viewer's card."""

    cards: tuple[PersonalizedCard, ...]



@dataclass(frozen=True)
class CheckedResult:
    """Fact-checker handoff: approved, revised, or replaced commentary and cards."""

    commentary: AgentOutcome[Commentary]
    commentary_check: FactCheckRecord
    cards: tuple[PersonalizedCard, ...]
