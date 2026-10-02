"""Match intelligence service: the end-to-end pipeline for one live match.

For each incoming event it interprets (stage 2), lets the producer pick moments, and runs the multi-agent workflow
(stages 3-5); at each period end it writes a recap. If the workflow itself fails, a degraded template path keeps output flowing.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from agent_framework import AgentFrameworkException
from pydantic import BaseModel

from insidegame.agents.context import MomentContext, build_moment_context, build_viewer_context
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


class MatchIntelligenceService:
    """Stateful pipeline for one match and one set of viewers."""

    def __init__(self, metadata: MatchMetadata, suite: AgentSuite, policy: RunPolicy,
                 viewers: Sequence[ViewerProfile]) -> None:
        self.analyzer = MatchAnalyzer(metadata)
        self.suite, self.policy = suite, policy
        self.viewers = tuple(build_viewer_context(v, metadata) for v in viewers)
        self.producer = ProducerPolicy()
        self.workflow = build_moment_workflow(suite, self.analyzer, policy)

    async def _broadcast(self, job: MomentJob) -> MomentBroadcast:
        match_id = self.analyzer.metadata.match_id
        try:
            outputs = (await self.workflow.run(job)).get_outputs()
        except AgentFrameworkException as exc:
            logger.error("Workflow failed for %s: %s", job.context.moment.moment_id, exc)
            outputs = []
        broadcasts = [o for o in outputs if isinstance(o, MomentBroadcast)]
        return broadcasts[0] if broadcasts else degraded_broadcast(match_id, job.context, job)

    async def handle_event(self, event: MatchEvent) -> EventResult:
        """Run the full pipeline for one incoming event."""
        update = self.analyzer.ingest(event)
        broadcasts = []
        for moment, audience in self.producer.select(update.moments, self.viewers):
            job = MomentJob(build_moment_context(moment, self.analyzer), audience)
            broadcasts.append(await self._broadcast(job))
        recap = None
        if event.event_type is EventType.PERIOD_END:
            stage = RecapStage.HALF_TIME if event.period == PERIODS[0] else RecapStage.FULL_TIME
            recap = await self.recap(stage)
        return EventResult(update, tuple(broadcasts), recap)

    async def recap(self, stage: RecapStage) -> AgentOutcome[MatchRecap]:
        """Write a recap of the match so far."""
        return await write_recap(self.suite, build_recap_context(self.analyzer, stage), self.analyzer, self.policy)
