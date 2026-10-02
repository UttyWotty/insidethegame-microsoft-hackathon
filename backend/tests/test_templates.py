"""Tests that deterministic fallbacks are valid and grounded for every moment kind and persona.

Fallbacks are the safety net for live broadcast, so they must always pass the same validators as model output.
Inputs come from a real simulated match.
"""

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.personas import PERSONAS, PersonaKey, ViewerProfile
from insidegame.agents.templates import commentary_template, explanation_template, persona_card_template
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind

MIN_KINDS_COVERED = 5


def _viewers(analyzer: MatchAnalyzer) -> list[ViewerContext]:
    home = analyzer.metadata.home
    scorer = home.players[-1]
    return [
        ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)),
        ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),
        ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=home.team_id), home.name),
        ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=scorer.player_id),
                      tracked_player_name=scorer.name),
        ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER)),
    ]


def test_fixture_covers_most_moment_kinds(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    assert len(analysed_match[1]) >= MIN_KINDS_COVERED


def test_every_template_passes_its_validator(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer, contexts = analysed_match
    for context in contexts.values():
        explanation = explanation_template(context)
        evidence = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
        assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None
        assert commentary_validator(lambda: evidence)(commentary_template(context, explanation)) is None
        for viewer in _viewers(analyzer):
            card = persona_card_template(context, explanation, viewer)
            problem = card_validator(lambda: evidence, viewer.viewer.profile.max_words)(card)
            assert problem is None, (context.moment.kind, viewer.viewer.persona, problem)


def test_persona_cards_differ_for_the_same_moment(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer, contexts = analysed_match
    context = contexts[MomentKind.GOAL]
    explanation = explanation_template(context)
    bodies = {persona_card_template(context, explanation, v).body for v in _viewers(analyzer)}
    assert len(bodies) >= len(PERSONAS) - 1
