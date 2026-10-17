"""Tests that outcome problems reach cue provenance and the producer desk, and only when there are any.

A degraded broadcast whose card or explanation template fails must carry the matching notes on each output's
provenance entry, and the producer record must pass them through unchanged. Outcomes without problems (model, retry
or fallback) must produce provenance entries with no problems key, so normal cues stay byte-identical.
"""

import asyncio
from collections.abc import Callable

import pytest
from test_live import OFFLINE_POLICY, _offline_suite

from insidegame.agents.context import MomentContext, ViewerContext, build_viewer_context
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import AgentOutcome, OutputSource
from insidegame.agents.schemas import Explanation, PersonaCard, TranslatedCard
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.core.exceptions import CardBudgetError
from insidegame.live.producer import ProducerDesk
from insidegame.orchestration import service
from insidegame.orchestration.cues import OverlayCue, build_cue
from insidegame.orchestration.messages import MomentJob, PersonalizedCard
from insidegame.orchestration.minimal_outputs import TEMPLATE_FAILED_NOTE
from insidegame.orchestration.service import WORKFLOW_DEGRADED_NOTE, MatchIntelligenceService, degraded_broadcast
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

MATCH_ID = "m-problems"
FAILING_VIEWER = "ca"
OUTCOME_ROLES = ("explanation", "commentary", "card")
DEGRADED = [WORKFLOW_DEGRADED_NOTE]
TEMPLATE_FAILED = [WORKFLOW_DEGRADED_NOTE, TEMPLATE_FAILED_NOTE]
RETRY_NOTE = "card exceeded 25 words"
LATENCY_MS = 120
SERVICE_SEED = 3


def _viewers(analyzer: MatchAnalyzer) -> tuple[ViewerContext, ...]:
    meta = analyzer.metadata
    profiles = [ViewerProfile("an", PersonaKey.ANALYST), ViewerProfile(FAILING_VIEWER, PersonaKey.CASUAL),
                ViewerProfile("sf", PersonaKey.SUPERFAN, "es", favourite_team_id=meta.home.team_id)]
    return tuple(build_viewer_context(p, meta) for p in profiles)


def _entry(cue: OverlayCue, role: str) -> dict[str, object]:
    entry = cue.provenance[role]
    assert isinstance(entry, dict)
    return entry


def _failing_card_for(viewer_id: str) -> Callable[[MomentContext, Explanation, ViewerContext], PersonaCard]:
    real = service.persona_card_template

    def flaky(context: MomentContext, explanation: Explanation, viewer: ViewerContext) -> PersonaCard:
        if viewer.viewer.viewer_id == viewer_id:
            raise CardBudgetError("prefix too long")
        return real(context, explanation, viewer)
    return flaky


def test_failing_card_template_marks_only_that_viewers_card(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "persona_card_template", _failing_card_for(FAILING_VIEWER))
    viewers = _viewers(analysed_match[0])
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, viewers))
    assert len(broadcast.cues) == len(viewers)
    for cue in broadcast.cues:
        assert _entry(cue, "explanation")["problems"] == DEGRADED
        assert _entry(cue, "commentary")["problems"] == DEGRADED
        expected = TEMPLATE_FAILED if cue.viewer_id == FAILING_VIEWER else DEGRADED
        assert _entry(cue, "card")["problems"] == expected
        assert "problems" not in cue.provenance["fact_check"]  # type: ignore[operator]


def test_failing_explanation_template_is_noted_on_every_cue(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(context: MomentContext) -> Explanation:
        raise KeyError("kind")
    monkeypatch.setattr(service, "explanation_template", fail)
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, _viewers(analysed_match[0])))
    for cue in broadcast.cues:
        assert _entry(cue, "explanation")["problems"] == TEMPLATE_FAILED
        assert _entry(cue, "commentary")["problems"] == DEGRADED


def test_producer_record_carries_the_problems(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "persona_card_template", _failing_card_for(FAILING_VIEWER))
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, _viewers(analysed_match[0])))
    record = ProducerDesk().record(broadcast).to_dict()
    assert record["degraded"] is True
    cards = {c["viewer_id"]: c["provenance"]["card"] for c in record["cues"]}  # type: ignore[index, union-attr]
    assert cards[FAILING_VIEWER]["problems"] == TEMPLATE_FAILED
    assert cards["an"]["problems"] == DEGRADED


def _normal_outcomes(context: MomentContext, viewer: ViewerContext, source: OutputSource,
                     problems: tuple[str, ...]) -> tuple[AgentOutcome[Explanation], AgentOutcome, PersonalizedCard]:
    explanation = service.explanation_template(context)
    commentary = service.commentary_template(context, explanation)
    card = service.persona_card_template(context, explanation, viewer)
    return (AgentOutcome(explanation, source, 1, LATENCY_MS, ()), AgentOutcome(commentary, source, 1, LATENCY_MS, ()),
            PersonalizedCard(viewer, AgentOutcome(card, source, 1, LATENCY_MS, problems)))


@pytest.mark.parametrize("source", list(OutputSource), ids=lambda s: s.value)
def test_outcomes_without_problems_have_no_problems_key(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        source: OutputSource) -> None:
    viewer = _viewers(analysed_match[0])[0]
    explanation, commentary, item = _normal_outcomes(goal_context, viewer, source, ())
    cue = build_cue(MATCH_ID, goal_context.moment, explanation, commentary, item)
    for role in OUTCOME_ROLES:
        assert _entry(cue, role) == {"source": source.value, "attempts": 1, "latency_ms": LATENCY_MS}


def test_retry_and_translation_problems_are_surfaced(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    viewer = _viewers(analysed_match[0])[2]
    explanation, commentary, item = _normal_outcomes(goal_context, viewer, OutputSource.MODEL_RETRY, (RETRY_NOTE,))
    translated = TranslatedCard(title="t", body="b", stat_labels=[])
    translation = AgentOutcome(translated, OutputSource.FALLBACK, 2, LATENCY_MS, ("timed out after 1.0s",) * 2)
    cue = build_cue(MATCH_ID, goal_context.moment, explanation, commentary,
                    PersonalizedCard(viewer, item.card, translation))
    assert _entry(cue, "card")["problems"] == [RETRY_NOTE]
    assert _entry(cue, "translation")["problems"] == ["timed out after 1.0s", "timed out after 1.0s"]
    assert "problems" not in _entry(cue, "explanation") and "problems" not in _entry(cue, "commentary")


def test_normal_offline_run_has_no_problems_anywhere() -> None:
    result = simulate_match(build_fixture("brookhaven", "silverlake", SERVICE_SEED))
    meta = result.metadata
    profiles = [ViewerProfile("an", PersonaKey.ANALYST), ViewerProfile("nc", PersonaKey.NEWCOMER, "fr")]
    pipeline = MatchIntelligenceService(meta, _offline_suite(), OFFLINE_POLICY, profiles)

    async def run() -> list[OverlayCue]:
        cues: list[OverlayCue] = []
        for event in result.events:
            outcome = await pipeline.handle_event(event)
            cues.extend(c for b in outcome.broadcasts for c in b.cues)
        return cues

    cues = asyncio.run(run())
    assert cues
    for cue in cues:
        roles = [r for r in ("explanation", "commentary", "card", "translation") if r in cue.provenance]
        assert all("problems" not in _entry(cue, r) for r in roles)
