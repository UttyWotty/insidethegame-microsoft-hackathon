"""Tests for the multi-agent moment workflow, the producer policy, and the match service.

A callback fake chat client stands in for the model so the full Agent Framework workflow runs without a server.
They cover parallel handoffs, translation, provenance, recaps, producer pacing, and degraded-mode recovery.
"""

import asyncio
import json
import re

from agent_framework import AgentFrameworkException
from fakes import CallbackChatClient

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import OutputSource, RunPolicy
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.domain.enums import EventType
from insidegame.orchestration.cues import CUE_DELAY_S
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.producer import MIN_GAP_S, ProducerPolicy
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.orchestration.workflow import build_moment_workflow
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

POLICY = RunPolicy(timeout_s=5.0, max_attempts=2, prompt_suffix="")
SPANISH = "es"
STANDOUT_PATTERN = re.compile(r'"standout_candidate": \{\s*"name": "([^"]+)"')
REPLIES = {
    "Match Analyst": {"headline": "A pivotal moment", "why_it_matters": "It shifts the balance.", "evidence": [],
                      "theme": "pressure_shift"},
    "Lead Commentator": {"line": "What a moment in this match!"},
    "Personalization Producer": {"title": "Big moment", "body": "This could decide it.", "stat_callouts": []},
    "broadcast translator": {"title": "Gran momento", "body": "Esto puede decidirlo.", "stat_labels": []},
}


def _respond(instructions: str, prompt: str) -> str:
    if "Match Editor" in instructions:
        name = STANDOUT_PATTERN.search(prompt)
        return json.dumps({"headline": "A tight contest", "summary": "Both sides fought hard.", "turning_points": [],
                           "standout_player": name.group(1) if name else "", "tactical_story": "Control decided it."})
    return json.dumps(next(v for k, v in REPLIES.items() if k in instructions))


def _viewers(analyzer: MatchAnalyzer) -> tuple[ViewerContext, ...]:
    home = analyzer.metadata.home
    return (ViewerContext(ViewerProfile("analyst-1", PersonaKey.ANALYST)),
            ViewerContext(ViewerProfile("fan-es", PersonaKey.SUPERFAN, SPANISH, home.team_id), home.name))


def test_workflow_produces_one_cue_per_viewer(
    goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer = analysed_match[0]
    client = CallbackChatClient(_respond)
    workflow = build_moment_workflow(create_agent_suite(client), analyzer, POLICY)
    outputs = asyncio.run(workflow.run(MomentJob(goal_context, _viewers(analyzer)))).get_outputs()
    broadcast = outputs[0]
    assert client.calls[0].startswith("You are the Match Analyst")
    assert {c.viewer_id for c in broadcast.cues} == {"analyst-1", "fan-es"}
    spanish = next(c for c in broadcast.cues if c.viewer_id == "fan-es")
    assert spanish.language == SPANISH and spanish.title == "Gran momento"
    assert spanish.provenance["translation"]["source"] == OutputSource.MODEL.value
    assert spanish.display_from_s == goal_context.moment.match_second + CUE_DELAY_S
    assert spanish.commentary == REPLIES["Lead Commentator"]["line"]


def test_full_match_runs_end_to_end_with_recaps() -> None:
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
    viewers = [ViewerProfile("a", PersonaKey.ANALYST), ViewerProfile("c", PersonaKey.CASUAL, "fr")]
    service = MatchIntelligenceService(result.metadata, create_agent_suite(CallbackChatClient(_respond)), POLICY,
                                       viewers)
    broadcasts, recaps = [], []
    for event in result.events:
        outcome = asyncio.run(service.handle_event(event))
        broadcasts.extend(outcome.broadcasts)
        if outcome.recap:
            recaps.append(outcome.recap)
    goals = sum(1 for e in result.events if e.event_type is EventType.GOAL)
    assert sum(b.context.moment.kind is MomentKind.GOAL for b in broadcasts) == goals
    assert len(recaps) == 2 and all(r.source is OutputSource.MODEL for r in recaps)
    assert all(not b.degraded and b.cues for b in broadcasts)


def test_broken_model_still_produces_grounded_fallback_output(goal_context: MomentContext,
                                                             analysed_match: tuple[MatchAnalyzer, dict]) -> None:
    analyzer = analysed_match[0]
    workflow = build_moment_workflow(create_agent_suite(CallbackChatClient(lambda i, p: "garbage")), analyzer, POLICY)
    broadcast = asyncio.run(workflow.run(MomentJob(goal_context, _viewers(analyzer)))).get_outputs()[0]
    assert broadcast.explanation.source is OutputSource.FALLBACK
    assert all(c.provenance["card"]["source"] == OutputSource.FALLBACK.value for c in broadcast.cues)
    assert all(c.body for c in broadcast.cues)


def test_service_degrades_when_workflow_fails(goal_context: MomentContext) -> None:
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
    service = MatchIntelligenceService(result.metadata, create_agent_suite(CallbackChatClient(_respond)), POLICY,
                                       [ViewerProfile("a", PersonaKey.ANALYST)])

    class BrokenWorkflow:
        async def run(self, job: MomentJob) -> None:
            raise AgentFrameworkException("executor crashed")

    service.workflow = BrokenWorkflow()  # type: ignore[assignment]
    broadcast = asyncio.run(service._broadcast(MomentJob(goal_context, service.viewers)))
    assert broadcast.degraded and broadcast.cues[0].body


def _moment(kind: MomentKind, second: float, importance: float = 0.6) -> KeyMoment:
    return KeyMoment(f"m{second}", kind, 1, second, importance, "brk")


def test_producer_enforces_gap_but_never_blocks_goals() -> None:
    viewers = (ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)),)
    producer = ProducerPolicy()
    assert producer.select((_moment(MomentKind.MOMENTUM_SWING, 100),), viewers)
    assert not producer.select((_moment(MomentKind.MOMENTUM_SWING, 100 + MIN_GAP_S / 2),), viewers)
    assert producer.select((_moment(MomentKind.GOAL, 100 + MIN_GAP_S / 2, 0.9),), viewers)


def test_producer_skips_moments_nobody_wants() -> None:
    casual_only = (ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),)
    assert not ProducerPolicy().select((_moment(MomentKind.CHAOS_SPELL, 50, 0.4),), casual_only)
