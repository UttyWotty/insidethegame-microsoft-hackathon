"""The fact-checking stage: verify drafts, send rejected cards back for one revision, and replace what still fails.

Model-written commentary and cards are checked by the roster rule and the fact-checker agent. A rejected card returns
to the personalizer with the issues; if the revision is rejected too, a grounded template replaces it.
"""

from dataclasses import replace
from typing import TypeVar

from pydantic import BaseModel

from insidegame.agents.context import MomentContext
from insidegame.agents.factory import AgentSuite
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.schemas import Commentary, Explanation, FactCheckVerdict, PersonaCard
from insidegame.agents.steps import fact_check, revise_card
from insidegame.agents.templates import commentary_template, persona_card_template
from insidegame.orchestration.messages import SKIPPED_CHECK, Checker, FactCheckRecord, PersonalizedCard, Verdict

TEMPLATE_ATTEMPTS: int = 0
TEMPLATE_LATENCY_MS: int = 0
CARD_KIND: str = "persona card"
COMMENTARY_KIND: str = "commentary line"
TEMPLATE_NOTE: str = "replaced after fact-check"

T = TypeVar("T", bound=BaseModel)


def card_text(card: PersonaCard) -> str:
    """The checkable text of a card."""
    return " ".join([card.title, card.body, *(f"{c.label} {c.value}" for c in card.stat_callouts)])


def _checker(outcome: AgentOutcome[FactCheckVerdict]) -> Checker:
    return Checker.RULES if outcome.source is OutputSource.FALLBACK else Checker.MODEL


def _template(value: T) -> AgentOutcome[T]:
    return AgentOutcome(value, OutputSource.FALLBACK, TEMPLATE_ATTEMPTS, TEMPLATE_LATENCY_MS, (TEMPLATE_NOTE,))


class FactCheckStage:
    """Applies the fact-checking policy to one moment's drafts."""

    def __init__(self, suite: AgentSuite, context: MomentContext, explanation: Explanation, squad: set[str],
                 policy: RunPolicy) -> None:
        self.suite, self.context, self.explanation, self.squad, self.policy = suite, context, explanation, squad, policy

    async def _verify(self, kind: str, text: str) -> AgentOutcome[FactCheckVerdict]:
        return await fact_check(self.suite, self.context, self.explanation, kind, text, self.squad, self.policy)

    async def commentary(self, draft: AgentOutcome[Commentary]) -> tuple[AgentOutcome[Commentary], FactCheckRecord]:
        """Check a commentary line, replacing it with the template line when rejected."""
        if draft.source is OutputSource.FALLBACK:
            return draft, SKIPPED_CHECK
        verdict = await self._verify(COMMENTARY_KIND, draft.value.line)
        if verdict.value.approved:
            return draft, FactCheckRecord(Verdict.APPROVED, _checker(verdict), (), verdict.latency_ms)
        record = FactCheckRecord(Verdict.REPLACED, _checker(verdict), tuple(verdict.value.issues), verdict.latency_ms)
        return _template(commentary_template(self.context, self.explanation)), record

    async def card(self, item: PersonalizedCard) -> PersonalizedCard:
        """Check a card; on rejection ask the personalizer to revise once, then fall back to the template."""
        if item.card.source is OutputSource.FALLBACK:
            return item
        verdict = await self._verify(CARD_KIND, card_text(item.card.value))
        if verdict.value.approved:
            return replace(item, fact_check=FactCheckRecord(Verdict.APPROVED, _checker(verdict), (), verdict.latency_ms))
        issues = tuple(verdict.value.issues)
        revised = await revise_card(self.suite, self.context, self.explanation, item.viewer, list(issues), self.policy)
        if revised.source is not OutputSource.FALLBACK:
            second = await self._verify(CARD_KIND, card_text(revised.value))
            if second.value.approved:
                latency = verdict.latency_ms + second.latency_ms
                return replace(item, card=revised,
                               fact_check=FactCheckRecord(Verdict.REVISED, _checker(second), issues, latency))
        template = _template(persona_card_template(self.context, self.explanation, item.viewer))
        return replace(item, card=template,
                       fact_check=FactCheckRecord(Verdict.REPLACED, _checker(verdict), issues, verdict.latency_ms))
