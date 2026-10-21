"""Tests that the Tactical Scout's shape_shift outputs stay grounded and that every check accepts them.

Shape shift moments in both directions, with and without a goal trigger, go through every fallback template and
persona card, which must stay grounded, while drafts citing metres or percentages absent from the facts must fail.
They also check the fact-check prompt, the analyst callouts, the glossary, labels, the reel, and the Scout's brief.
"""

import pytest
from shape_helpers import fixture, shape_moment

from insidegame.agents.context import MomentContext, ViewerContext, build_moment_context
from insidegame.agents.glossary import concept_for
from insidegame.agents.grounding import check_grounding
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.prompts import SCOUT_INSTRUCTIONS, fact_check_prompt
from insidegame.agents.templates import KIND_LABELS, commentary_template, explanation_template, persona_card_template
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.analytics.recap_basis import RecapStage
from insidegame.analytics.shape_tracker import ShiftDirection
from insidegame.highlights.reel import KIND_TITLES, select_moments

CASES = [(direction, trigger) for direction in ShiftDirection for trigger in (True, False)]


def _context(direction: ShiftDirection, with_trigger: bool) -> MomentContext:
    metadata = fixture()
    return build_moment_context(shape_moment(metadata, direction, with_trigger), MatchAnalyzer(metadata))


def _viewers(context: MomentContext) -> list[ViewerContext]:
    home = fixture().home
    tracked = home.players[-1]
    return [ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)), ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),
            ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=home.team_id), home.name),
            ViewerContext(ViewerProfile("r", PersonaKey.SUPERFAN, favourite_team_id="irv"), fixture().away.name),
            ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=tracked.player_id),
                          tracked_player_name=tracked.name),
            ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER))]


@pytest.mark.parametrize(("direction", "with_trigger"), CASES)
def test_shape_template_commentary_and_every_persona_card_are_grounded(direction: ShiftDirection,
                                                                      with_trigger: bool) -> None:
    context = _context(direction, with_trigger)
    facts = context.moment.facts
    explanation = explanation_template(context)
    assert str(facts["line_after_m"]) in explanation.headline and str(facts["summary"]) in explanation.why_it_matters
    assert explanation.why_it_matters.startswith("After going ahead at 78'") == with_trigger
    evidence = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None
    commentary = commentary_template(context, explanation)
    assert commentary_validator(lambda: evidence)(commentary) is None and commentary.line.endswith(".")
    for viewer in _viewers(context):
        card = persona_card_template(context, explanation, viewer)
        assert card_validator(lambda: evidence, viewer.viewer.profile.max_words)(card) is None, viewer.viewer.persona
        texts = [card.title, card.body, *(c.value for c in card.stat_callouts)]
        assert check_grounding(texts, context.to_prompt_dict()).grounded, viewer.viewer.persona


def test_shape_drafts_citing_absent_metres_or_percentages_fail_grounding() -> None:
    context = _context(ShiftDirection.DROPPED, True)
    evidence = context.to_prompt_dict()
    assert not check_grounding(["Their back line dropped to 45 m."], evidence).grounded
    assert not check_grounding(["They now hold 80% of the pitch."], evidence).grounded
    cited = f"The line dropped to {context.moment.facts['line_after_m']} m."
    assert check_grounding([cited], evidence).grounded


def test_shape_fact_check_prompt_and_analyst_callouts_carry_the_numbers() -> None:
    context = _context(ShiftDirection.DROPPED, True)
    prompt = fact_check_prompt(context, explanation_template(context), "card", "draft")
    assert "line_before_m" in prompt and "control_after_pct" in prompt
    card = persona_card_template(context, explanation_template(context), ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)))
    labels = [c.label for c in card.stat_callouts]
    assert "Back line (m)" in labels
    assert labels == ["Back line (m)", "Space control (%)", "Possession (%)"]


def test_shape_kind_has_a_concept_a_label_a_title_and_is_never_clipped() -> None:
    term, meaning = concept_for(MomentKind.SHAPE_SHIFT)
    assert term == "Defensive line" and meaning
    assert KIND_LABELS[MomentKind.SHAPE_SHIFT.value] == "shape shift"
    assert KIND_TITLES[MomentKind.SHAPE_SHIFT] == "Shape shift"
    moment = shape_moment(fixture(), ShiftDirection.DROPPED, True)
    assert select_moments([moment], RecapStage.FULL_TIME) == []


def test_scout_instructions_cover_shape_shifts_without_matching_the_analyst() -> None:
    assert "shape shift" in SCOUT_INSTRUCTIONS and "Match Analyst" not in SCOUT_INSTRUCTIONS
