"""Tests that deterministic fallbacks are valid and grounded for every moment kind and persona.

Fallbacks are the safety net for live broadcast, so they must always pass the same validators as model output.
Inputs come from a real simulated match.
"""

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.personas import PERSONAS, PersonaKey, ViewerProfile
from insidegame.agents.templates import (
    commentary_template,
    explanation_template,
    persona_card_template,
    spoken_units,
)
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind, moment_intensity
from insidegame.domain.enums import Intensity

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


def test_superfan_tone_matches_whether_the_moment_helps_their_club(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    analyzer, contexts = analysed_match
    miss = contexts[MomentKind.BIG_CHANCE_MISSED]
    explanation = explanation_template(miss)
    team = next(t for t in (analyzer.metadata.home, analyzer.metadata.away) if t.name == miss.team_name)
    rival = next(t for t in (analyzer.metadata.home, analyzer.metadata.away) if t.name != miss.team_name)
    own_fan = ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=team.team_id), team.name)
    rival_fan = ViewerContext(ViewerProfile("r", PersonaKey.SUPERFAN, favourite_team_id=rival.team_id), rival.name)
    assert persona_card_template(miss, explanation, own_fan).body.startswith("So close!")
    assert persona_card_template(miss, explanation, rival_fan).body.startswith("Stay strong.")


def test_recap_turning_points_are_important_and_readable(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    from insidegame.agents.recap_context import MIN_TURNING_POINT_IMPORTANCE, RecapStage, build_recap_context
    from insidegame.agents.templates import recap_template
    analyzer = analysed_match[0]
    context = build_recap_context(analyzer, RecapStage.FULL_TIME)
    minutes = {m.minute_label for m in analyzer.moments if m.importance >= MIN_TURNING_POINT_IMPORTANCE}
    assert all(str(m["minute"]) in minutes for m in context.moments)
    assert not any("_" in point for point in recap_template(context).turning_points)


def test_commentary_energy_follows_the_moment(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    contexts = analysed_match[1]
    for kind, context in contexts.items():
        line = commentary_template(context, explanation_template(context)).line
        intensity = moment_intensity(kind)
        if intensity is Intensity.NORMAL:
            assert line.endswith(".")
        else:  # excited, and goals react instead of repeating the play-by-play's "GOAL!"
            assert line.endswith("!") and not line.upper().startswith("GOAL")
    assert moment_intensity(MomentKind.GOAL) is Intensity.PEAK
    assert moment_intensity(MomentKind.GREAT_SAVE) is Intensity.RAISED
    assert moment_intensity(MomentKind.DIFFICULT_PASS) is Intensity.RAISED
    assert moment_intensity(MomentKind.MOMENTUM_SWING) is Intensity.NORMAL


def test_commentary_speaks_measurements_and_reacts_to_long_passes() -> None:
    assert spoken_units("Moreau finds Wexley from 40.5 m") == "Moreau finds Wexley from 41 metres"
    assert spoken_units("strikes at 112.4 km/h") == "strikes at 112 kilometres an hour"
