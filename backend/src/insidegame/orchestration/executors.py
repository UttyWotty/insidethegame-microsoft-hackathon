"""Agent Framework executors forming the per-moment multi-agent workflow.

Intake writes the job to shared workflow state, the analyst explains, the narrator and personalizer run in parallel,
and the assembler joins their results into overlay cues using the shared state written upstream.
"""

import asyncio

from agent_framework import Executor, WorkflowContext, handler

from insidegame.agents.context import ViewerContext
from insidegame.agents.factory import AgentSuite
from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.schemas import Explanation
from insidegame.agents.steps import explain, narrate, personalize, translate, translate_line
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.orchestration.cues import MomentBroadcast, build_cue
from insidegame.orchestration.messages import (
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
        """Record the job and forward it to the analyst."""
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
    """Runs the Personalization Producer and Translator agents for every viewer concurrently."""

    def __init__(self, suite: AgentSuite, policy: RunPolicy) -> None:
        super().__init__(id="personalizer")
        self.suite, self.policy = suite, policy

    async def _for_viewer(self, explained: ExplainedMoment, viewer: ViewerContext) -> PersonalizedCard:
        card = await personalize(self.suite, explained.job.context, explained.explanation.value, viewer, self.policy)
        if viewer.viewer.language == DEFAULT_LANGUAGE:
            return PersonalizedCard(viewer, card)
        translation = await translate(self.suite, card.value, viewer.viewer.language, self.policy)
        return PersonalizedCard(viewer, card, translation)

    @handler
    async def run(self, explained: ExplainedMoment, ctx: WorkflowContext[PersonalizationResult]) -> None:
        """Personalize, and translate where needed, for each viewer in the audience."""
        cards = await asyncio.gather(*(self._for_viewer(explained, v) for v in explained.job.viewers))
        await ctx.send_message(PersonalizationResult(tuple(cards)))


class AssemblerExecutor(Executor):
    """Joins narration and personalization into overlay cues, translating commentary for non-English viewers."""

    def __init__(self, match_id: str, suite: AgentSuite, policy: RunPolicy) -> None:
        super().__init__(id="assembler")
        self.match_id, self.suite, self.policy = match_id, suite, policy

    async def _commentary_by_language(self, line: str, languages: set[str]) -> dict[str, str]:
        targets = sorted(languages - {DEFAULT_LANGUAGE})
        outcomes = await asyncio.gather(*(translate_line(self.suite, line, lang, self.policy) for lang in targets))
        return {lang: o.value.line for lang, o in zip(targets, outcomes, strict=True)
                if o.source is not OutputSource.FALLBACK}

    @handler
    async def run(
        self, results: list[NarrationResult | PersonalizationResult], ctx: WorkflowContext[None, MomentBroadcast]
    ) -> None:
        """Build one cue per viewer and yield the moment broadcast."""
        job: MomentJob = ctx.get_state(JOB_STATE_KEY)
        explanation: AgentOutcome[Explanation] = ctx.get_state(EXPLANATION_STATE_KEY)
        narration = next(r for r in results if isinstance(r, NarrationResult))
        personalization = next(r for r in results if isinstance(r, PersonalizationResult))
        moment = job.context.moment
        languages = {item.viewer.viewer.language for item in personalization.cards}
        translated = await self._commentary_by_language(narration.commentary.value.line, languages)
        cues = tuple(build_cue(self.match_id, moment, explanation, narration.commentary, item,
                               translated.get(item.viewer.viewer.language))
                     for item in personalization.cards)
        await ctx.yield_output(MomentBroadcast(job.context, explanation, narration.commentary, cues))
