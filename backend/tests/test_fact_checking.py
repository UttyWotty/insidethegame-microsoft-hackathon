"""Tests for the fact-checking stage: roster rule, approval, revision handoff, replacement, and provenance.

A scripted fake model plays the Standards Editor and the Personalization Producer so each path is deterministic.
The workflow test checks that every cue carries its fact-check record.
"""

import asyncio
import json

from fakes import ScriptedChatClient

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.roster_check import unknown_players
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.schemas import PersonaCard
from insidegame.agents.templates import commentary_template, explanation_template
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration.fact_checking import FactCheckStage
from insidegame.orchestration.messages import PersonalizedCard, Verdict

POLICY = RunPolicy(timeout_s=5.0, max_attempts=1, prompt_suffix="")
EDITOR, PRODUCER = "Broadcast Standards Editor", "Personalization Producer"
APPROVE = json.dumps({"approved": True, "issues": []})
REJECT = json.dumps({"approved": False, "issues": ["The shot was saved, not scored."]})
REVISED = json.dumps({"title": "Saved!", "body": "A fine stop keeps it level.", "stat_callouts": []})


def _squad(analyzer: MatchAnalyzer) -> set[str]:
    return {p.name for t in (analyzer.metadata.home, analyzer.metadata.away) for p in t.players}


def _model_card(text: str) -> AgentOutcome[PersonaCard]:
    return AgentOutcome(PersonaCard(title="Big moment", body=text, stat_callouts=[]), OutputSource.MODEL, 1, 10, ())


def _run(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]], script: list[str],
         body: str = "What a goal!") -> tuple[PersonalizedCard, ScriptedChatClient]:
    analyzer, contexts = analysed_match
    context = contexts[MomentKind.GOAL]
    client = ScriptedChatClient({EDITOR: [s for s in script if "approved" in s],
                                 PRODUCER: [s for s in script if "approved" not in s]})
    stage = FactCheckStage(create_agent_suite(client), context, explanation_template(context), _squad(analyzer), POLICY)
    item = PersonalizedCard(ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)), _model_card(body))
    return asyncio.run(stage.card(item)), client


def test_roster_rule_flags_invented_players_only() -> None:
    squad = {"Jonas Quarry", "Hugo Varga"}
    assert unknown_players(["Jonas Quarry scores, assisted by Felix Novak."], squad) == ["Felix Novak"]
    assert unknown_players(["Jonas Quarry and Hugo Varga at Brookhaven Park."], squad) == []


def test_accurate_card_is_approved_by_the_model(analysed_match) -> None:  # noqa: ANN001
    checked, _ = _run(analysed_match, [APPROVE])
    assert checked.fact_check.verdict is Verdict.APPROVED and checked.fact_check.checker.value == "model"


def test_rejected_card_goes_back_to_the_personalizer_and_is_revised(analysed_match) -> None:  # noqa: ANN001
    checked, client = _run(analysed_match, [REJECT, REVISED, APPROVE])
    assert checked.fact_check.verdict is Verdict.REVISED
    assert checked.card.value.title == "Saved!" and checked.fact_check.issues == ("The shot was saved, not scored.",)
    revision_prompt = next(m for key, m, _ in client.requests if key == PRODUCER)[-1].text
    assert "The shot was saved, not scored." in revision_prompt


def test_card_rejected_twice_is_replaced_by_the_template(analysed_match) -> None:  # noqa: ANN001
    checked, _ = _run(analysed_match, [REJECT, REVISED, REJECT])
    assert checked.fact_check.verdict is Verdict.REPLACED and checked.card.source is OutputSource.FALLBACK


def test_invented_player_is_rejected_without_a_model_call(analysed_match) -> None:  # noqa: ANN001
    checked, client = _run(analysed_match, [REVISED, APPROVE], body="Felix Novak buries it!")
    assert checked.fact_check.checker.value in {"rules", "model"}
    assert "Felix Novak is not playing in this match" in checked.fact_check.issues
    assert not any(key == EDITOR for key, *_ in client.requests[:1])


def test_template_outputs_skip_review(analysed_match) -> None:  # noqa: ANN001
    analyzer, contexts = analysed_match
    context = contexts[MomentKind.GOAL]
    explanation = explanation_template(context)
    client = ScriptedChatClient({EDITOR: []})
    stage = FactCheckStage(create_agent_suite(client), context, explanation, _squad(analyzer), POLICY)
    template_line = AgentOutcome(commentary_template(context, explanation), OutputSource.FALLBACK, 0, 0, ())
    line, record = asyncio.run(stage.commentary(template_line))
    assert record.verdict is Verdict.SKIPPED and line is template_line and not client.requests
