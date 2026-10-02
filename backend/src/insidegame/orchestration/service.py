"""Match intelligence service: the end-to-end pipeline for one live match.

For each incoming event it interprets (stage 2), lets the producer pick moments, and runs the multi-agent workflow
(stages 3-5); at each period end it writes a recap. If the workflow itself fails, a degraded template path keeps output flowing.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from agent_framework import AgentFrameworkException, Workflow
from pydantic import BaseModel

from insidegame.agents.context import MomentContext, ViewerContext, build_moment_context, build_viewer_context
from insidegame.agents.factory import AgentSuite
from insidegame.agents.personas import ViewerProfile
from insidegame.agents.recap_context import RecapStage, build_recap_context
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.schemas import MatchRecap
from insidegame.agents.steps import write_recap
from insidegame.agents.templates import commentary_template, explanation_template, persona_card_template
from insidegame.analytics.analyzer import AnalysisUpdate, MatchAnalyzer
from insidegame.core.constants import PERIODS
from insidegame.domain.enums import EventType
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.orchestration.cues import MomentBroadcast, build_cue
from insidegame.orchestration.messages import MomentJob, PersonalizedCard
from insidegame.orchestration.producer import ProducerPolicy
from insidegame.orchestration.workflow import build_moment_workflow

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
WorkflowFactory = Callable[[AgentSuite, MatchAnalyzer, RunPolicy], Workflow]

DEGRADED_ATTEMPTS: int = 0
DEGRADED_LATENCY_MS: int = 0


@dataclass(frozen=True)
class EventResult:
    """Everything the pipeline produced for one event.

    Defaults: recap is None except on period-end events.
    """

    update: AnalysisUpdate
    broadcasts: tuple[MomentBroadcast, ...]
    recap: AgentOutcome[MatchRecap] | None = None


def _template_outcome(value: T) -> AgentOutcome[T]:
    return AgentOutcome(value, OutputSource.FALLBACK, DEGRADED_ATTEMPTS, DEGRADED_LATENCY_MS, ("workflow degraded",))


def _tracked_players(audience: tuple[ViewerContext, ...]) -> tuple[str, ...]:
    return tuple(v.viewer.favourite_player_id for v in audience if v.viewer.favourite_player_id)


def degraded_broadcast(match_id: str, context: MomentContext, job: MomentJob) -> MomentBroadcast:
    """Build a broadcast purely from templates when the workflow cannot run."""
    explanation = _template_outcome(explanation_template(context))
    commentary = _template_outcome(commentary_template(context, explanation.value))
    cues = tuple(
        build_cue(match_id, context.moment, explanation, commentary,
                  PersonalizedCard(viewer, _template_outcome(persona_card_template(context, explanation.value, viewer))))
        for viewer in job.viewers
    )
    return MomentBroadcast(context, explanation, commentary, cues, degraded=True)


@dataclass(frozen=True)
class Interpretation:
    """Fast, synchronous result of interpreting one event.

    Defaults: recap_stage is None except on period-end events; contexts is empty when no moment was detected.
    contexts holds one prompt context per new key moment, whether or not any viewer received it.
    """

    update: AnalysisUpdate
    jobs: tuple[MomentJob, ...]
    recap_stage: RecapStage | None = None
    contexts: tuple[MomentContext, ...] = ()


class MatchIntelligenceService:
    """Stateful pipeline for one match and a changing set of viewer segments."""

    def __init__(self, metadata: MatchMetadata, suite: AgentSuite, policy: RunPolicy,
                 viewers: Sequence[ViewerProfile], workflow_factory: WorkflowFactory | None = None) -> None:
        """Create the pipeline; workflow_factory defaults to build_moment_workflow."""
        self.analyzer = MatchAnalyzer(metadata)
        self.suite, self.policy = suite, policy
        self.workflow_factory = workflow_factory or build_moment_workflow
        self.viewers: dict[str, ViewerContext] = {}
        for viewer in viewers:
            self.add_viewer(viewer)
        self.producer = ProducerPolicy()

    def add_viewer(self, viewer: ViewerProfile) -> ViewerContext:
        """Register a viewer segment so future moments are personalized for it."""
        context = build_viewer_context(viewer, self.analyzer.metadata)
        self.viewers[viewer.viewer_id] = context
        return context

    def remove_viewer(self, viewer_id: str) -> None:
        """Stop personalizing for a viewer segment."""
        self.viewers.pop(viewer_id, None)

    def interpret(self, event: MatchEvent) -> Interpretation:
        """Interpret an event and decide which moments to send to the agents, without awaiting them."""
        update = self.analyzer.ingest(event)
        jobs = tuple(MomentJob(build_moment_context(moment, self.analyzer, _tracked_players(audience)), audience)
                     for moment, audience in self.producer.select(update.moments, tuple(self.viewers.values())))
        stage = None
        if event.event_type is EventType.PERIOD_END:
            stage = RecapStage.HALF_TIME if event.period == PERIODS[0] else RecapStage.FULL_TIME
        contexts = tuple(build_moment_context(moment, self.analyzer) for moment in update.moments)
        return Interpretation(update, jobs, stage, contexts)

    async def produce(self, job: MomentJob) -> MomentBroadcast:
        """Run the multi-agent workflow for one job, degrading to templates if the workflow fails."""
        match_id = self.analyzer.metadata.match_id
        workflow = self.workflow_factory(self.suite, self.analyzer, self.policy)
        try:
            outputs = (await workflow.run(job)).get_outputs()
        except AgentFrameworkException as exc:
            logger.error("Workflow failed for %s: %s", job.context.moment.moment_id, exc)
            outputs = []
        broadcasts = [o for o in outputs if isinstance(o, MomentBroadcast)]
        return broadcasts[0] if broadcasts else degraded_broadcast(match_id, job.context, job)

    async def handle_event(self, event: MatchEvent) -> EventResult:
        """Run the full pipeline for one event sequentially; convenient for batch runs and tests."""
        interpretation = self.interpret(event)
        broadcasts = tuple([await self.produce(job) for job in interpretation.jobs])
        recap = await self.recap(interpretation.recap_stage) if interpretation.recap_stage else None
        return EventResult(interpretation.update, broadcasts, recap)

    async def recap(self, stage: RecapStage) -> AgentOutcome[MatchRecap]:
        """Write a recap of the match so far."""
        return await write_recap(self.suite, build_recap_context(self.analyzer, stage), self.analyzer, self.policy)
