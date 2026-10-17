"""Tests that the degraded broadcast path survives templates that raise, at the service and the live-session level.

Each template is forced to fail with several exception types (no network), and the broadcast must still carry one valid
cue per viewer with the template-failed note and a logged error; a single failing card leaves other viewers untouched.
A live session whose workflow and templates both fail must still publish cues to every subscribed segment.
"""

import asyncio
import json
import logging
from collections.abc import Callable

import pytest
from test_live import OFFLINE_POLICY, SPEED, _instant, _offline_suite

from insidegame.agents.context import MomentContext, ViewerContext, build_viewer_context
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.schemas import Explanation, PersonaCard, StatCallout
from insidegame.agents.templates import EXPLAINERS
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.core.exceptions import CardBudgetError
from insidegame.live.segments import build_segment_profile
from insidegame.live.session import LiveMessage, MatchSession, MessageType
from insidegame.orchestration import service
from insidegame.orchestration.cues import MomentBroadcast, OverlayCue
from insidegame.orchestration.messages import MomentJob, PersonalizedCard
from insidegame.orchestration.minimal_outputs import TEMPLATE_FAILED_NOTE, minimal_explanation
from insidegame.orchestration.service import WORKFLOW_DEGRADED_NOTE, MatchIntelligenceService, degraded_broadcast
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

MATCH_ID = "m-degraded"
SERVICE_LOGGER = "insidegame.orchestration.service"
FAILURES: tuple[Exception, ...] = (CardBudgetError("prefix too long"), KeyError("kind"), ValueError("bad fact"),
                                   ZeroDivisionError("division"))
TEMPLATE_NAMES = ("explanation_template", "commentary_template", "persona_card_template")
SESSION_PERSONAS = ("analyst", "casual", "newcomer")


def _viewers(analyzer: MatchAnalyzer) -> tuple[ViewerContext, ...]:
    meta = analyzer.metadata
    profiles = [ViewerProfile("an", PersonaKey.ANALYST), ViewerProfile("ca", PersonaKey.CASUAL),
                ViewerProfile("sf", PersonaKey.SUPERFAN, "es", favourite_team_id=meta.home.team_id),
                ViewerProfile("pt", PersonaKey.PLAYER_TRACKER, favourite_player_id=meta.home.players[0].player_id),
                ViewerProfile("nc", PersonaKey.NEWCOMER)]
    return tuple(build_viewer_context(p, meta) for p in profiles)


def _raiser(error: Exception) -> Callable[..., object]:
    def fail(*args: object) -> object:
        raise error
    return fail


def _card_of(cue: OverlayCue) -> PersonaCard:
    return PersonaCard(title=cue.title, body=cue.body, stat_callouts=[StatCallout(**c) for c in cue.stat_callouts])


def _assert_valid(broadcast: MomentBroadcast, context: MomentContext, viewers: tuple[ViewerContext, ...]) -> None:
    explanation = broadcast.explanation.value
    evidence = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None
    assert commentary_validator(lambda: evidence)(broadcast.commentary.value) is None
    assert [c.viewer_id for c in broadcast.cues] == [v.viewer.viewer_id for v in viewers]
    for cue, viewer in zip(broadcast.cues, viewers, strict=True):
        assert card_validator(lambda: evidence, viewer.viewer.profile.max_words)(_card_of(cue)) is None
        assert cue.provenance["card"]["source"] == "fallback" and cue.body


def _record_cards(monkeypatch: pytest.MonkeyPatch) -> list[PersonalizedCard]:
    """Wrap build_cue in the service so each viewer's card outcome (and its notes) can be inspected."""
    items: list[PersonalizedCard] = []
    real = service.build_cue

    def recording(match_id: str, moment: object, explanation: object, commentary: object,
                  item: PersonalizedCard) -> OverlayCue:
        items.append(item)
        return real(match_id, moment, explanation, commentary, item)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "build_cue", recording)
    return items


def _failure_logs(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == SERVICE_LOGGER and r.levelno == logging.ERROR and r.exc_info]


@pytest.mark.parametrize("error", FAILURES, ids=lambda e: type(e).__name__)
def test_failing_explanation_template_uses_the_minimal_explanation(
        analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]], monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture, error: Exception) -> None:
    monkeypatch.setattr(service, "explanation_template", _raiser(error))
    viewers = _viewers(analysed_match[0])
    for context in analysed_match[1].values():
        caplog.clear()
        broadcast = degraded_broadcast(MATCH_ID, context, MomentJob(context, viewers))
        assert broadcast.degraded and broadcast.explanation.value == minimal_explanation(context)
        assert broadcast.explanation.problems == (WORKFLOW_DEGRADED_NOTE, TEMPLATE_FAILED_NOTE)
        assert TEMPLATE_FAILED_NOTE not in broadcast.commentary.problems
        _assert_valid(broadcast, context, viewers)
        assert len(_failure_logs(caplog)) == 1


def test_unexpected_moment_kind_degrades_to_the_minimal_explanation(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.delitem(EXPLAINERS, MomentKind.GOAL)
    viewers = _viewers(analysed_match[0])
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, viewers))
    assert broadcast.explanation.value == minimal_explanation(goal_context)
    assert TEMPLATE_FAILED_NOTE in broadcast.explanation.problems
    _assert_valid(broadcast, goal_context, viewers)
    assert _failure_logs(caplog)


@pytest.mark.parametrize("error", FAILURES, ids=lambda e: type(e).__name__)
def test_failing_commentary_template_uses_the_headline(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error: Exception) -> None:
    monkeypatch.setattr(service, "commentary_template", _raiser(error))
    viewers = _viewers(analysed_match[0])
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, viewers))
    assert broadcast.commentary.value.line == broadcast.explanation.value.headline
    assert broadcast.commentary.problems == (WORKFLOW_DEGRADED_NOTE, TEMPLATE_FAILED_NOTE)
    assert TEMPLATE_FAILED_NOTE not in broadcast.explanation.problems
    assert all(c.commentary == broadcast.explanation.value.headline for c in broadcast.cues)
    _assert_valid(broadcast, goal_context, viewers)
    assert len(_failure_logs(caplog)) == 1


@pytest.mark.parametrize("error", FAILURES, ids=lambda e: type(e).__name__)
def test_every_template_failing_still_gives_every_viewer_a_valid_cue(
        analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]], monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture, error: Exception) -> None:
    for name in TEMPLATE_NAMES:
        monkeypatch.setattr(service, name, _raiser(error))
    items = _record_cards(monkeypatch)
    viewers = _viewers(analysed_match[0])
    for context in analysed_match[1].values():
        caplog.clear()
        items.clear()
        broadcast = degraded_broadcast(MATCH_ID, context, MomentJob(context, viewers))
        headline = minimal_explanation(context).headline
        assert broadcast.commentary.value.line == headline
        assert all(c.title == headline and c.body == headline and not c.stat_callouts for c in broadcast.cues)
        assert all(TEMPLATE_FAILED_NOTE in i.card.problems for i in items) and len(items) == len(viewers)
        _assert_valid(broadcast, context, viewers)
        assert len(_failure_logs(caplog)) == 2 + len(viewers)


def test_one_failing_card_leaves_other_viewers_byte_identical(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    viewers = _viewers(analysed_match[0])
    normal = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, viewers))
    failing_id = "ca"
    real = service.persona_card_template

    def flaky(context: MomentContext, explanation: Explanation, viewer: ViewerContext) -> PersonaCard:
        if viewer.viewer.viewer_id == failing_id:
            raise CardBudgetError("prefix too long")
        return real(context, explanation, viewer)
    monkeypatch.setattr(service, "persona_card_template", flaky)
    items = _record_cards(monkeypatch)
    broadcast = degraded_broadcast(MATCH_ID, goal_context, MomentJob(goal_context, viewers))
    for before, after, item in zip(normal.cues, broadcast.cues, items, strict=True):
        if after.viewer_id == failing_id:
            assert after.title == after.body == broadcast.explanation.value.headline
            assert TEMPLATE_FAILED_NOTE in item.card.problems
        else:
            assert json.dumps(after.to_dict(), sort_keys=True) == json.dumps(before.to_dict(), sort_keys=True)
            assert item.card.problems == (WORKFLOW_DEGRADED_NOTE,)
    assert broadcast.explanation == normal.explanation and broadcast.commentary == normal.commentary
    _assert_valid(broadcast, goal_context, viewers)
    assert len(_failure_logs(caplog)) == 1


class BrokenService(MatchIntelligenceService):
    """Offline service whose workflow always fails with an unexpected error."""

    async def produce(self, job: MomentJob, observer: object = None) -> MomentBroadcast:  # type: ignore[override]
        raise RuntimeError("workflow boom")


def _drain(queue: asyncio.Queue[LiveMessage]) -> list[LiveMessage]:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def test_session_publishes_cues_when_workflow_and_templates_fail(
        goal_context: MomentContext, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    for name in TEMPLATE_NAMES:
        monkeypatch.setattr(service, name, _raiser(ValueError("template boom")))
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))

    async def scenario() -> tuple[MatchSession, dict[str, list[LiveMessage]]]:
        session = MatchSession("d", result, BrokenService(result.metadata, _offline_suite(), OFFLINE_POLICY, ()),
                               SPEED, _instant)
        subscribers = [session.subscribe(build_segment_profile(p)) for p in SESSION_PERSONAS]
        for subscriber in subscribers:
            _drain(subscriber.queue)
        job = MomentJob(goal_context, tuple(session.service.viewers.values()))
        await session._produce(job, skip_if_stale=False)
        return session, {s.segment_id: _drain(s.queue) for s in subscribers}

    session, received = asyncio.run(scenario())
    headline = minimal_explanation(goal_context).headline
    assert len(received) == len(SESSION_PERSONAS)
    for segment, messages in received.items():
        cues = [m for m in messages if m.type is MessageType.CUE]
        assert len(cues) == 1 and cues[0].data["viewer_id"] == segment and cues[0].data["body"] == headline
    assert session.desk.records[goal_context.moment.moment_id].degraded
    assert any("Production failed" in r.getMessage() for r in caplog.records)
    assert len(_failure_logs(caplog)) == 2 + len(SESSION_PERSONAS)
