"""Tests for the minimal last-resort outputs used when a degraded-path template raises.

They check the minimal explanation's fixed shape and grounding for every moment kind, including added-time minutes.
They also check that the minimal commentary and card pass their validators for every persona, even for long headlines.
"""

from dataclasses import replace

import pytest

from insidegame.agents.context import MomentContext, ViewerContext, build_viewer_context
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.schemas import Explanation
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration.minimal_outputs import (
    MINIMAL_THEME,
    MINIMAL_WHY_IT_MATTERS,
    kind_title,
    minimal_card,
    minimal_commentary,
    minimal_explanation,
)

ADDED_TIME_SECOND = 45 * 60 + 150.0
LONG_HEADLINE_WORDS = 200


def _viewers(analyzer: MatchAnalyzer) -> list[ViewerContext]:
    meta = analyzer.metadata
    profiles = [ViewerProfile("an", PersonaKey.ANALYST), ViewerProfile("ca", PersonaKey.CASUAL),
                ViewerProfile("sf", PersonaKey.SUPERFAN, favourite_team_id=meta.home.team_id),
                ViewerProfile("pt", PersonaKey.PLAYER_TRACKER, favourite_player_id=meta.home.players[0].player_id),
                ViewerProfile("nc", PersonaKey.NEWCOMER)]
    return [build_viewer_context(p, meta) for p in profiles]


def kind_title_of(kind: MomentKind) -> str:
    return kind.value.replace("_", " ").capitalize()


def test_kind_title_is_readable(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    contexts = analysed_match[1]
    assert kind_title(contexts[MomentKind.GOAL]) == "Goal"
    assert kind_title(contexts[MomentKind.BIG_CHANCE_MISSED]) == "Big chance missed"


def test_minimal_explanation_is_grounded_for_every_kind(
        analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    for kind, context in analysed_match[1].items():
        explanation = minimal_explanation(context)
        assert explanation.headline == f"{context.moment.minute_label} {kind_title(context)}"
        assert kind_title(context) == kind_title_of(kind)
        assert explanation.why_it_matters == MINIMAL_WHY_IT_MATTERS
        assert explanation.evidence == [] and explanation.theme is MINIMAL_THEME
        assert explanation_validator(lambda c=context: [c.to_prompt_dict()])(explanation) is None


def test_minimal_explanation_is_grounded_in_added_time(goal_context: MomentContext) -> None:
    moment = replace(goal_context.moment, period=1, match_second=ADDED_TIME_SECOND)
    context = replace(goal_context, moment=moment)
    explanation = minimal_explanation(context)
    assert "+" in explanation.headline
    assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None


def test_minimal_commentary_is_the_headline_and_valid(goal_context: MomentContext) -> None:
    explanation = minimal_explanation(goal_context)
    line = minimal_commentary(explanation)
    assert line.line == explanation.headline
    evidence = [goal_context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert commentary_validator(lambda: evidence)(line) is None


@pytest.mark.parametrize("headline_words", [None, LONG_HEADLINE_WORDS])
def test_minimal_card_passes_the_card_validator_for_every_persona(
        analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]], goal_context: MomentContext,
        headline_words: int | None) -> None:
    explanation = minimal_explanation(goal_context)
    if headline_words is not None:
        explanation = Explanation(headline=" ".join(["word"] * headline_words), why_it_matters="",
                                  evidence=[], theme=MINIMAL_THEME)
    evidence = [goal_context.to_prompt_dict(), explanation.model_dump(mode="json")]
    for viewer in _viewers(analysed_match[0]):
        max_words = viewer.viewer.profile.max_words
        card = minimal_card(explanation, max_words)
        assert card.title == explanation.headline and card.stat_callouts == []
        assert card_validator(lambda: evidence, max_words)(card) is None
