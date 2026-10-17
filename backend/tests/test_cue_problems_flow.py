"""Tests that problems recorded by real resilient agent runs (a retried answer, a timed-out translation) reach cues.

The analyst is scripted to give an ungrounded answer first and a grounded one second, so its outcome is a retry
whose rejection note must appear on the explanation provenance. The translator is scripted to respond too slowly,
so its fallback's timeout note must appear on the translation provenance while the commentary stays clean.
"""

import asyncio
import json

from fakes import ScriptedChatClient

from insidegame.agents.context import MomentContext, build_viewer_context
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import AgentOutcome, OutputSource, RunPolicy
from insidegame.agents.steps import explain, translate
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration import service
from insidegame.orchestration.cues import build_cue
from insidegame.orchestration.messages import PersonalizedCard

POLICY = RunPolicy(timeout_s=5.0, max_attempts=2, prompt_suffix="")
FAST_TIMEOUT = RunPolicy(timeout_s=0.05, max_attempts=2, prompt_suffix="")
SLOW_RESPONSE_S = 0.5
ANALYST_KEY, TRANSLATOR_KEY = "Match Analyst", "broadcast translator"
UNGROUNDED_NUMBER = 987
MATCH_ID = "m-flow"
LANGUAGE = "fr"


def _explanation_json(context: MomentContext, extra: str = "") -> str:
    scorer = context.moment.facts["scorer"]
    return json.dumps({"headline": f"{scorer} strikes{extra}", "why_it_matters": "It changes the game.",
                       "evidence": [f"xG {context.moment.facts['xg']}"], "theme": "clinical_finishing"})


def test_real_retry_and_timeout_notes_reach_cue_provenance(
        goal_context: MomentContext, analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    analyzer = analysed_match[0]
    analyst_client = ScriptedChatClient({ANALYST_KEY: [
        _explanation_json(goal_context, f" for the {UNGROUNDED_NUMBER}th time"), _explanation_json(goal_context)]})
    explanation = asyncio.run(explain(create_agent_suite(analyst_client), goal_context, analyzer, POLICY))
    assert explanation.source is OutputSource.MODEL_RETRY and len(explanation.problems) == 1

    viewer = build_viewer_context(ViewerProfile("ca", PersonaKey.CASUAL, LANGUAGE), analyzer.metadata)
    card = service.persona_card_template(goal_context, explanation.value, viewer)
    slow = ScriptedChatClient({TRANSLATOR_KEY: ["{}"]}, delay_s=SLOW_RESPONSE_S)
    translation = asyncio.run(translate(create_agent_suite(slow), card, LANGUAGE, FAST_TIMEOUT))
    assert translation.source is OutputSource.FALLBACK and translation.problems

    commentary = AgentOutcome(service.commentary_template(goal_context, explanation.value), OutputSource.MODEL, 1, 0, ())
    item = PersonalizedCard(viewer, AgentOutcome(card, OutputSource.MODEL, 1, 0, ()), translation)
    cue = build_cue(MATCH_ID, goal_context.moment, explanation, commentary, item)
    entry = cue.provenance["explanation"]
    assert isinstance(entry, dict)
    assert entry["source"] == OutputSource.MODEL_RETRY.value and entry["attempts"] == 2
    assert entry["problems"] == list(explanation.problems)
    assert str(UNGROUNDED_NUMBER) in entry["problems"][0]
    translated = cue.provenance["translation"]
    assert isinstance(translated, dict) and translated["problems"] == list(translation.problems)
    assert all("problems" not in cue.provenance[role] for role in ("commentary", "card"))  # type: ignore[operator]
