"""Tests for the resilient agent steps using a scripted fake chat client.

They cover accepted output, retry after a grounding rejection, fallback after repeated failure or timeout,
persona-specific prompting, translation integrity, and tool evidence acceptance.
"""

import asyncio
import json

from fakes import ScriptedChatClient

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import OutputSource, RunPolicy
from insidegame.agents.schemas import PersonaCard, StatCallout
from insidegame.agents.steps import explain, narrate, personalize, translate
from insidegame.agents.templates import explanation_template
from insidegame.agents.tools import EvidenceLedger, build_analyst_tools
from insidegame.agents.validation import explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind

POLICY = RunPolicy(timeout_s=5.0, max_attempts=2, prompt_suffix="")
FAST_TIMEOUT = RunPolicy(timeout_s=0.05, max_attempts=2, prompt_suffix="")
SLOW_RESPONSE_S = 0.5
ANALYST_KEY, NARRATOR_KEY = "Match Analyst", "Lead Commentator"
PERSONALIZER_KEY, TRANSLATOR_KEY = "Personalization Producer", "broadcast translator"
UNGROUNDED_NUMBER = 987


def _explanation_json(context: MomentContext, extra: str = "") -> str:
    scorer = context.moment.facts["scorer"]
    return json.dumps({"headline": f"{scorer} strikes{extra}", "why_it_matters": "It changes the game.",
                       "evidence": [f"xG {context.moment.facts['xg']}"], "theme": "clinical_finishing"})


def test_grounded_answer_is_accepted(goal_context: MomentContext,
                                     analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    client = ScriptedChatClient({ANALYST_KEY: [_explanation_json(goal_context)]})
    outcome = asyncio.run(explain(create_agent_suite(client), goal_context, analysed_match[0], POLICY))
    assert outcome.source is OutputSource.MODEL and outcome.attempts == 1
    assert client.requests[0][2]["response_format"].__name__ == "Explanation"


def test_ungrounded_answer_is_retried_with_feedback(
    goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    client = ScriptedChatClient({ANALYST_KEY: [_explanation_json(goal_context, f" for the {UNGROUNDED_NUMBER}th time"),
                                               _explanation_json(goal_context)]})
    outcome = asyncio.run(explain(create_agent_suite(client), goal_context, analysed_match[0], POLICY))
    assert outcome.source is OutputSource.MODEL_RETRY
    assert str(UNGROUNDED_NUMBER) in outcome.problems[0]
    assert "rejected" in client.requests[1][1][-1].text


def test_repeated_invalid_output_falls_back_to_template(
    goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    client = ScriptedChatClient({ANALYST_KEY: ["not json", "{}"]})
    outcome = asyncio.run(explain(create_agent_suite(client), goal_context, analysed_match[0], POLICY))
    assert outcome.source is OutputSource.FALLBACK
    assert outcome.value == explanation_template(goal_context)


def test_timeout_falls_back_without_retrying(goal_context: MomentContext) -> None:
    client = ScriptedChatClient({NARRATOR_KEY: ['{"line": "Goal!"}'] * 2}, delay_s=SLOW_RESPONSE_S)
    outcome = asyncio.run(narrate(create_agent_suite(client), goal_context, explanation_template(goal_context),
                                  FAST_TIMEOUT))
    assert outcome.source is OutputSource.FALLBACK and len(client.requests) == 1


def test_personalizer_prompt_carries_persona_specifics(goal_context: MomentContext) -> None:
    card = json.dumps({"title": "Big goal", "body": "We needed that.", "stat_callouts": []})
    client = ScriptedChatClient({PERSONALIZER_KEY: [card, card]})
    suite, explanation = create_agent_suite(client), explanation_template(goal_context)
    fan = ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id="kba"), "Kestrel Bay Athletic")
    learner = ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER))
    assert asyncio.run(personalize(suite, goal_context, explanation, fan, POLICY)).source is OutputSource.MODEL
    asyncio.run(personalize(suite, goal_context, explanation, learner, POLICY))
    fan_prompt, learner_prompt = (client.requests[i][1][-1].text for i in (0, 1))
    assert "Kestrel Bay Athletic" in fan_prompt and "partisan" in fan_prompt
    assert "concept_to_teach" in learner_prompt and "concept_to_teach" not in fan_prompt


def test_translation_that_changes_numbers_is_rejected() -> None:
    card = PersonaCard(title="Goal in minute 68", body="A 93 km/h strike.",
                       stat_callouts=[StatCallout(label="Shot speed", value="93")])
    bad = json.dumps({"title": "Gol en el minuto 86", "body": "Un disparo a 93 km/h.", "stat_labels": ["Velocidad"]})
    client = ScriptedChatClient({TRANSLATOR_KEY: [bad, bad]})
    outcome = asyncio.run(translate(create_agent_suite(client), card, "es", POLICY))
    assert outcome.source is OutputSource.FALLBACK and outcome.value.title == card.title


def test_numbers_from_tool_results_are_grounded(
    goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    ledger = EvidenceLedger()
    compare = next(t for t in build_analyst_tools(analysed_match[0], ledger) if t.name == "compare_teams")
    asyncio.run(compare.invoke(arguments={}))
    pressures = next(iter(ledger.entries[0]["payload"].values()))["pressures"]
    explanation = explanation_template(goal_context).model_copy(update={"evidence": [f"{pressures} pressures"]})
    assert explanation_validator(lambda: [goal_context.to_prompt_dict()])(explanation) is not None
    assert explanation_validator(lambda: [goal_context.to_prompt_dict(), ledger.entries])(explanation) is None


def test_fenced_json_from_local_models_is_accepted(goal_context: MomentContext) -> None:
    fenced = '```json\n{"line": "What a strike!"}\n```'
    client = ScriptedChatClient({NARRATOR_KEY: [fenced]})
    outcome = asyncio.run(narrate(create_agent_suite(client), goal_context, explanation_template(goal_context), POLICY))
    assert outcome.source is OutputSource.MODEL and outcome.value.line == "What a strike!"


def test_concurrency_gate_serialises_calls_and_times_only_the_call(goal_context: MomentContext) -> None:
    slow = 0.05
    gated = RunPolicy(timeout_s=slow * 3, max_attempts=1, prompt_suffix="", gate=None)

    async def scenario() -> list[OutputSource]:
        policy = RunPolicy(gated.timeout_s, 1, "", False, asyncio.Semaphore(1))
        client = ScriptedChatClient({NARRATOR_KEY: ['{"line": "Goal!"}'] * 4}, delay_s=slow)
        suite, explanation = create_agent_suite(client), explanation_template(goal_context)
        outcomes = await asyncio.gather(*(narrate(suite, goal_context, explanation, policy) for _ in range(4)))
        return [o.source for o in outcomes]

    assert asyncio.run(scenario()) == [OutputSource.MODEL] * 4


def test_tracked_player_stats_reach_the_personalizer(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    from insidegame.agents.context import build_moment_context
    analyzer = analysed_match[0]
    moment = next(m for m in analyzer.moments if m.player_ids)
    tracked = next(p for p in analyzer.metadata.home.players if p.player_id not in moment.player_ids)
    context = build_moment_context(moment, analyzer, (tracked.player_id,))
    assert tracked.name in context.to_prompt_dict()["players"]
    card = json.dumps({"title": "t", "body": "b", "stat_callouts": []})
    client = ScriptedChatClient({PERSONALIZER_KEY: [card]})
    viewer = ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=tracked.player_id),
                           tracked_player_name=tracked.name)
    asyncio.run(personalize(create_agent_suite(client), context, explanation_template(context), viewer, POLICY))
    prompt = client.requests[0][1][-1].text
    assert f"{tracked.name}'s point of view" in prompt


def test_tools_answer_as_of_the_moment_not_the_live_match(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer, contexts = analysed_match
    early = min(contexts.values(), key=lambda c: (c.moment.period, c.moment.match_second))
    ledger = EvidenceLedger()
    tools = {t.name: t for t in build_analyst_tools(analyzer, ledger, as_of=early)}
    asyncio.run(tools["compare_teams"].invoke(arguments={}))
    asyncio.run(tools["recent_moments"].invoke(arguments={"count": 8}))
    assert ledger.entries[0]["payload"] == early.teams
    cutoff = (early.moment.period, early.moment.match_second)
    visible = [m for m in analyzer.moments if (m.period, m.match_second) <= cutoff]
    assert len(visible) < len(analyzer.moments)
    assert [e["minute"] for e in ledger.entries[1]["payload"]] == [m.minute_label for m in visible[-8:]]


def test_recap_take_uses_the_model_when_grounded_and_falls_back_otherwise(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    from insidegame.agents.recap_context import RecapStage, build_recap_context
    from insidegame.agents.steps import personalize_recap
    from insidegame.agents.templates import recap_template
    analyzer = analysed_match[0]
    context = build_recap_context(analyzer, RecapStage.HALF_TIME)
    recap = recap_template(context)
    viewer = ViewerContext(ViewerProfile("a", PersonaKey.ANALYST))
    good = json.dumps({"headline": "Tight first half", "take": "Very little between the sides."})
    bad = json.dumps({"headline": "Rout", "take": "They had 987 shots."})
    client = ScriptedChatClient({PERSONALIZER_KEY: [good, bad, bad]})
    suite = create_agent_suite(client)
    accepted = asyncio.run(personalize_recap(suite, context, recap, viewer, POLICY))
    rejected = asyncio.run(personalize_recap(suite, context, recap, viewer, POLICY))
    assert accepted.source is OutputSource.MODEL and accepted.value.headline == "Tight first half"
    assert rejected.source is OutputSource.FALLBACK and "numbers at half-time" in rejected.value.headline
    assert "The Analyst" in client.requests[0][1][-1].text
