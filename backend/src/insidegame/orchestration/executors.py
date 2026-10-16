"""Agent Framework executors forming the per-moment multi-agent workflow.

Intake writes the job to shared state, the analyst (or the Tactical Scout, for tactical flags) explains, the narrator
and personalizer run in parallel, the fact-checker verifies (and sends rejected cards back for revision), and the
assembler translates and builds cues.
"""

import asyncio

from agent_framework import Executor, WorkflowContext, handler

from insidegame.agents.context import ViewerContext
from insidegame.agents.factory import AgentSuite
from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.schemas import Explanation
from insidegame.agents.steps import explain, narrate, personalize, scout_explain, translate, translate_line
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration.cues import MomentBroadcast, build_cue
from insidegame.orchestration.fact_checking import FactCheckStage
from insidegame.orchestration.messages import (
    CheckedResult,
    ExplainedMoment,
    MomentJob,
    NarrationResult,
    PersonalizationResult,
    PersonalizedCard,
)

JOB_STATE_KEY: str = "job"
EXPLANATION_STATE_KEY: str = "explanation"


class IntakeExecutor(Executor):
    """Publishes the job to shared state and starts the pipeline."""

    def __init__(self) -> None:
        super().__init__(id="intake")

    @handler
    async def accept(self, job: MomentJob, ctx: WorkflowContext[MomentJob]) -> None:
        """Record the job and forward it to the analyst or the Tactical Scout."""
        ctx.set_state(JOB_STATE_KEY, job)
        await ctx.send_message(job)


class AnalystExecutor(Executor):
    """Runs the Match Analyst agent."""

    def __init__(self, suite: AgentSuite, analyzer: MatchAnalyzer, policy: RunPolicy) -> None:
        super().__init__(id="analyst")
        self.suite, self.analyzer, self.policy = suite, analyzer, policy

    @handler
    async def run(self, job: MomentJob, ctx: WorkflowContext[ExplainedMoment]) -> None:
        """Explain the moment and share the explanation."""
        outcome = await explain(self.suite, job.context, self.analyzer, self.policy)
        ctx.set_state(EXPLANATION_STATE_KEY, outcome)
        await ctx.send_message(ExplainedMoment(job, outcome))


def is_tactical(job: object) -> bool:
    """Edge condition: True for a tactical_pattern job, which the Tactical Scout explains instead of the analyst."""
    return isinstance(job, MomentJob) and job.context.moment.kind is MomentKind.TACTICAL_PATTERN


def is_not_tactical(job: object) -> bool:
    """Edge condition: True for every job the Match Analyst explains."""
    return isinstance(job, MomentJob) and not is_tactical(job)


class ScoutExecutor(Executor):
    """Runs the Tactical Scout agent on tactical_pattern moments."""

    def __init__(self, suite: AgentSuite, analyzer: MatchAnalyzer, policy: RunPolicy) -> None:
        super().__init__(id="scout")
        self.suite, self.analyzer, self.policy = suite, analyzer, policy

    @handler
    async def run(self, job: MomentJob, ctx: WorkflowContext[ExplainedMoment]) -> None:
        """Explain the flagged pattern and share the explanation, exactly as the analyst would."""
        outcome = await scout_explain(self.suite, job.context, self.analyzer, self.policy)
        ctx.set_state(EXPLANATION_STATE_KEY, outcome)
        await ctx.send_message(ExplainedMoment(job, outcome))


class NarratorExecutor(Executor):
    """Runs the Lead Commentator agent."""

    def __init__(self, suite: AgentSuite, policy: RunPolicy) -> None:
        super().__init__(id="narrator")
        self.suite, self.policy = suite, policy

    @handler
    async def run(self, explained: ExplainedMoment, ctx: WorkflowContext[NarrationResult]) -> None:
        """Write the commentary line."""
        outcome = await narrate(self.suite, explained.job.context, explained.explanation.value, self.policy)
        await ctx.send_message(NarrationResult(outcome))


class PersonalizerExecutor(Executor):
    """Runs the Personalization Producer for every viewer concurrently."""

    def __init__(self, suite: AgentSuite, policy: RunPolicy) -> None:
        super().__init__(id="personalizer")
        self.suite, self.policy = suite, policy

    @handler
    async def run(self, explained: ExplainedMoment, ctx: WorkflowContext[PersonalizationResult]) -> None:
        """Write one persona card per viewer segment."""
        cards = await asyncio.gather(*(
            personalize(self.suite, explained.job.context, explained.explanation.value, viewer, self.policy)
            for viewer in explained.job.viewers))
        items = tuple(PersonalizedCard(viewer, card) for viewer, card in zip(explained.job.viewers, cards, strict=True))
        await ctx.send_message(PersonalizationResult(items))


class FactCheckerExecutor(Executor):
    """Runs the Standards Editor over commentary and every card before anything goes to air."""

    def __init__(self, suite: AgentSuite, squad: set[str], policy: RunPolicy) -> None:
        super().__init__(id="fact_checker")
        self.suite, self.squad, self.policy = suite, squad, policy

    @handler
    async def run(
        self, results: list[NarrationResult | PersonalizationResult], ctx: WorkflowContext[CheckedResult]
    ) -> None:
        """Verify, revise, or replace each draft, then hand the checked set to the assembler."""
        job: MomentJob = ctx.get_state(JOB_STATE_KEY)
        explanation: AgentOutcome[Explanation] = ctx.get_state(EXPLANATION_STATE_KEY)
        narration = next(r for r in results if isinstance(r, NarrationResult))
        personalization = next(r for r in results if isinstance(r, PersonalizationResult))
        stage = FactCheckStage(self.suite, job.context, explanation.value, self.squad, self.policy)
        (commentary, commentary_check), cards = await asyncio.gather(
            stage.commentary(narration.commentary), asyncio.gather(*(stage.card(c) for c in personalization.cards)))
        await ctx.send_message(CheckedResult(commentary, commentary_check, tuple(cards)))


class AssemblerExecutor(Executor):
    """Translates checked output for non-English viewers and builds the overlay cues."""

    def __init__(self, match_id: str, suite: AgentSuite, policy: RunPolicy) -> None:
        super().__init__(id="assembler")
        self.match_id, self.suite, self.policy = match_id, suite, policy

    async def _commentary_by_language(self, line: str, languages: set[str]) -> dict[str, str]:
        targets = sorted(languages - {DEFAULT_LANGUAGE})
        outcomes = await asyncio.gather(*(translate_line(self.suite, line, lang, self.policy) for lang in targets))
        return {lang: o.value.line for lang, o in zip(targets, outcomes, strict=True)
                if o.source is not OutputSource.FALLBACK}

    async def _translate(self, item: PersonalizedCard) -> PersonalizedCard:
        if item.viewer.viewer.language == DEFAULT_LANGUAGE:
            return item
        translation = await translate(self.suite, item.card.value, item.viewer.viewer.language, self.policy)
        return PersonalizedCard(item.viewer, item.card, translation, item.fact_check)

    @handler
    async def run(self, checked: CheckedResult, ctx: WorkflowContext[None, MomentBroadcast]) -> None:
        """Build one cue per viewer and yield the moment broadcast."""
        job: MomentJob = ctx.get_state(JOB_STATE_KEY)
        explanation: AgentOutcome[Explanation] = ctx.get_state(EXPLANATION_STATE_KEY)
        languages = {item.viewer.viewer.language for item in checked.cards}
        translated, cards = await asyncio.gather(
            self._commentary_by_language(checked.commentary.value.line, languages),
            asyncio.gather(*(self._translate(item) for item in checked.cards)))
        moment = job.context.moment
        cues = tuple(build_cue(self.match_id, moment, explanation, checked.commentary, item,
                               translated.get(item.viewer.viewer.language), checked.commentary_check)
                     for item in cards)
        await ctx.yield_output(MomentBroadcast(job.context, explanation, checked.commentary, cues))
