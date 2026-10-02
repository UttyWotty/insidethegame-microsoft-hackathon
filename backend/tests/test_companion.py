"""Tests for the Match Companion question-answering agent and its API endpoint.

They cover grounded acceptance, rejection of invented numbers, the persona and language reaching the prompt,
the offline fallback through the API, and input validation.
"""

import asyncio
import json

from fakes import ScriptedChatClient
from test_api import _client

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.question_context import build_question_context
from insidegame.agents.runner import OutputSource, RunPolicy
from insidegame.agents.steps import answer_question
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind

POLICY = RunPolicy(timeout_s=5.0, max_attempts=2, prompt_suffix="")
COMPANION_KEY = "Match Companion"
QUESTION = "Who has been the best player so far?"


def _answer(text: str) -> str:
    return json.dumps({"answer": text, "stat_callouts": [], "follow_ups": ["Which team is pressing more?"]})


def test_grounded_answer_is_accepted_with_persona_and_language(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer = analysed_match[0]
    context = build_question_context(analyzer)
    best = context.top_players[0]
    client = ScriptedChatClient({COMPANION_KEY: [_answer(f"{best['name']} has completed {best['passes_completed']} passes.")]})
    viewer = ViewerContext(ViewerProfile("v", PersonaKey.NEWCOMER, "fr"))
    outcome = asyncio.run(answer_question(create_agent_suite(client), QUESTION, context, viewer, analyzer, POLICY))
    assert outcome.source is OutputSource.MODEL
    prompt = client.requests[0][1][-1].text
    assert '"answer_language": "fr"' in prompt and "The Newcomer" in prompt and QUESTION in prompt


def test_invented_numbers_fall_back_to_the_grounded_summary(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer = analysed_match[0]
    context = build_question_context(analyzer)
    invented = _answer("He has scored 987 goals this season.")
    client = ScriptedChatClient({COMPANION_KEY: [invented, invented]})
    viewer = ViewerContext(ViewerProfile("v", PersonaKey.CASUAL))
    outcome = asyncio.run(answer_question(create_agent_suite(client), QUESTION, context, viewer, analyzer, POLICY))
    assert outcome.source is OutputSource.FALLBACK
    assert context.scoreline in outcome.value.answer and "987" in outcome.problems[0]


def test_ask_endpoint_answers_offline_and_validates_input() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"seed": 3}).json()["session_id"]
        response = client.post(f"/api/matches/{session_id}/ask", json={"question": QUESTION, "persona": "analyst"})
        body = response.json()
        assert response.status_code == 200 and body["source"] == "fallback" and body["answer"]
        assert client.post(f"/api/matches/{session_id}/ask", json={"question": "?"}).status_code == 422
        assert client.post("/api/matches/missing/ask", json={"question": QUESTION}).status_code == 404
