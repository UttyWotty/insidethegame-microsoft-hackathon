"""Tests for the multi-agent moment workflow, the producer policy, and the match service.

A callback fake chat client stands in for the model so the full Agent Framework workflow runs without a server.
They cover parallel handoffs, translation, provenance, recaps, producer pacing, and degraded-mode recovery.
"""

import asyncio
import json
import re

from agent_framework import AgentFrameworkException
import pytest
from fakes import CallbackChatClient
from shape_helpers import shape_moment

from insidegame.agents.context import MomentContext, ViewerContext, build_moment_context
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import OutputSource, RunPolicy
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.analytics.shape_tracker import ShiftDirection
from insidegame.domain.enums import EventType
from insidegame.orchestration.cues import CUE_DELAY_S, TIME_DECIMALS
from insidegame.orchestration.executors import SCOUT_KINDS, is_not_tactical, is_tactical
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
    "Tactical Scout": {"headline": "A pattern is forming", "why_it_matters": "One flank keeps opening up.",
                       "evidence": [], "theme": "control"},
    "Lead Commentator": {"line": "What a moment in this match!"},
    "Personalization Producer": {"title": "Big moment", "body": "This could decide it.", "stat_callouts": []},
    "broadcast translator": {"title": "Gran momento", "body": "Esto puede decidirlo.", "stat_labels": []},
    "Broadcast Standards Editor": {"approved": True, "issues": []},
}


SPANISH_LINE = "¡Qué momento en este partido!"


def _respond(instructions: str, prompt: str) -> str:
    if "Translate this commentary line" in prompt:
        return json.dumps({"line": SPANISH_LINE})
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
    assert spanish.provenance["fact_check"]["verdict"] == "approved"
    assert spanish.provenance["commentary_check"]["verdict"] == "approved"
    assert spanish.display_from_s == round(goal_context.moment.match_second + CUE_DELAY_S, TIME_DECIMALS)
    assert spanish.commentary == SPANISH_LINE and spanish.commentary_language == SPANISH
    english = next(c for c in broadcast.cues if c.viewer_id == "analyst-1")
    assert english.commentary == REPLIES["Lead Commentator"]["line"] and english.commentary_language == "en"
    assert all(c.commentary_intensity == "peak" for c in broadcast.cues)  # the fixture moment is a goal


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
    spanish = next(c for c in broadcast.cues if c.viewer_id == "fan-es")
    assert spanish.language == spanish.commentary_language == "en"  # untranslated text is labelled English


def test_service_degrades_when_workflow_fails(goal_context: MomentContext) -> None:
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))

    class BrokenWorkflow:
        def run(self, job: MomentJob, stream: bool = False) -> None:
            raise AgentFrameworkException("executor crashed")

    service = MatchIntelligenceService(result.metadata, create_agent_suite(CallbackChatClient(_respond)), POLICY,
                                       [ViewerProfile("a", PersonaKey.ANALYST)],
                                       workflow_factory=lambda *args: BrokenWorkflow())  # type: ignore[arg-type,return-value]
    broadcast = asyncio.run(service.produce(MomentJob(goal_context, tuple(service.viewers.values()))))
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


def test_goal_does_not_block_its_own_milestone() -> None:
    viewers = (ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)),)
    goal, brace = _moment(MomentKind.GOAL, 600, 0.9), _moment(MomentKind.MILESTONE, 600, 0.7)
    chosen = ProducerPolicy().select((goal, brace), viewers)
    assert [m.kind for m, _ in chosen] == [MomentKind.GOAL, MomentKind.MILESTONE]


def _route(context: MomentContext, analyzer: MatchAnalyzer) -> tuple[list[str], object, dict[str, list[str]]]:
    prompts: dict[str, list[str]] = {}

    def record(instructions: str, prompt: str) -> str:
        prompts.setdefault(instructions.split(".")[0], []).append(prompt)
        return _respond(instructions, prompt)

    client = CallbackChatClient(record)
    workflow = build_moment_workflow(create_agent_suite(client), analyzer, POLICY)
    outputs = asyncio.run(workflow.run(MomentJob(context, _viewers(analyzer)))).get_outputs()
    return client.calls, outputs[0], prompts


def test_tactical_job_runs_the_scout_and_never_the_analyst(
    tactical_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    calls, broadcast, prompts = _route(tactical_context, analysed_match[0])
    assert calls[0].startswith("You are the Tactical Scout")
    assert not any(c.startswith("You are the Match Analyst") for c in calls)
    scout_reply = REPLIES["Tactical Scout"]
    for agent in ("Lead Commentator", "Personalization Producer", "Broadcast Standards Editor"):
        received = next(v for k, v in prompts.items() if agent in k)
        assert all(scout_reply["headline"] in prompt for prompt in received), agent
    assert broadcast.explanation.value.headline == scout_reply["headline"]
    assert broadcast.explanation.source is OutputSource.MODEL and len(broadcast.cues) == 2
    assert all(c.provenance["explanation"]["source"] == OutputSource.MODEL.value for c in broadcast.cues)
    assert all(c.commentary_intensity == "normal" for c in broadcast.cues)


def test_goal_job_runs_the_analyst_and_never_the_tactical_scout(
    goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    calls, broadcast, _ = _route(goal_context, analysed_match[0])
    assert calls[0].startswith("You are the Match Analyst")
    assert not any(c.startswith("You are the Tactical Scout") for c in calls)
    assert broadcast.explanation.value.headline == REPLIES["Match Analyst"]["headline"]


def test_broken_model_on_a_tactical_job_falls_back_to_the_scout_template(
    tactical_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    from insidegame.agents.templates import explanation_template
    analyzer = analysed_match[0]
    workflow = build_moment_workflow(create_agent_suite(CallbackChatClient(lambda i, p: "garbage")), analyzer, POLICY)
    broadcast = asyncio.run(workflow.run(MomentJob(tactical_context, _viewers(analyzer)))).get_outputs()[0]
    assert broadcast.explanation.source is OutputSource.FALLBACK
    assert broadcast.explanation.value == explanation_template(tactical_context)
    assert all(c.body for c in broadcast.cues)


@pytest.fixture(scope="module")
def shape_context(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> MomentContext:
    """A dropped shape_shift moment with a goal trigger, in the fixture match's context."""
    analyzer = analysed_match[0]
    return build_moment_context(shape_moment(analyzer.metadata, ShiftDirection.DROPPED, True), analyzer)


def test_shape_shift_job_runs_the_scout_and_never_the_analyst(
    shape_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    calls, broadcast, _ = _route(shape_context, analysed_match[0])
    assert calls[0].startswith("You are the Tactical Scout")
    assert not any(c.startswith("You are the Match Analyst") for c in calls)
    assert broadcast.explanation.value.headline == REPLIES["Tactical Scout"]["headline"]
    assert broadcast.explanation.source is OutputSource.MODEL and len(broadcast.cues) == 2


def test_shape_shift_routing_edges_send_only_scout_kinds_to_the_scout(
    shape_context: MomentContext, goal_context: MomentContext,
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    viewers = _viewers(analysed_match[0])
    assert SCOUT_KINDS == frozenset({MomentKind.TACTICAL_PATTERN, MomentKind.SHAPE_SHIFT})
    shape_job, goal_job = MomentJob(shape_context, viewers), MomentJob(goal_context, viewers)
    assert is_tactical(shape_job) and not is_not_tactical(shape_job)
    assert is_not_tactical(goal_job) and not is_tactical(goal_job)


def test_broken_model_on_a_shape_shift_job_falls_back_to_the_shape_template(
    shape_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    from insidegame.agents.templates import explanation_template
    analyzer = analysed_match[0]
    workflow = build_moment_workflow(create_agent_suite(CallbackChatClient(lambda i, p: "garbage")), analyzer, POLICY)
    broadcast = asyncio.run(workflow.run(MomentJob(shape_context, _viewers(analyzer)))).get_outputs()[0]
    assert broadcast.explanation.source is OutputSource.FALLBACK
    assert broadcast.explanation.value == explanation_template(shape_context)
    assert "back line" in broadcast.explanation.value.headline and all(c.body for c in broadcast.cues)
