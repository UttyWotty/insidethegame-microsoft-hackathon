"""Tests that agents can cite expected threat (xT) and that the grounding and validation checks accept it.

A threat_created moment from a tracked simulated match goes through every fallback template and persona card,
which must stay grounded, while drafts citing xT or bypass numbers absent from the facts must fail grounding.
They also check labels, the glossary, the analyst callouts, and the xT keys in moment and question context.
"""

import pytest
from threat_helpers import TrackedMatch, analyse_with_tracking

from insidegame.agents.context import PLAYER_CONTEXT_KEYS, MomentContext, ViewerContext, build_moment_context
from insidegame.agents.glossary import concept_for
from insidegame.agents.grounding import check_grounding, collect_evidence_numbers
from insidegame.agents.personas import PERSONAS, PersonaKey, ViewerProfile
from insidegame.agents.prompts import ANALYST_INSTRUCTIONS, fact_check_prompt
from insidegame.agents.question_context import build_question_context
from insidegame.agents.templates import KIND_LABELS, commentary_template, explanation_template, persona_card_template
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.moments import MomentKind
from insidegame.highlights.reel import KIND_TITLES

MAX_ABSENT = 99
DECIMAL_STEP = 100


@pytest.fixture(scope="module")
def tracked() -> TrackedMatch:
    return analyse_with_tracking("kestrel_bay", "ironvale", 7)


@pytest.fixture(scope="module")
def threat_context(tracked: TrackedMatch) -> MomentContext:
    """Context for the first threat_created moment, rebuilt against the full-time analyzer state."""
    moment = next(m for m in tracked.analyzer.moments if m.kind is MomentKind.THREAT_CREATED)
    return build_moment_context(moment, tracked.analyzer)


def _viewers(context: MomentContext, tracked: TrackedMatch) -> list[ViewerContext]:
    teams = {t.name: t for t in (tracked.result.metadata.home, tracked.result.metadata.away)}
    team = teams[str(context.team_name)]
    passer = next(p for p in team.players if p.player_id == context.moment.player_ids[0])
    return [ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)), ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),
            ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=team.team_id), team.name),
            ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=passer.player_id),
                          tracked_player_name=passer.name),
            ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER))]


def _absent(evidence: set[float], decimal: bool) -> float:
    candidates = ([n / DECIMAL_STEP for n in range(MAX_ABSENT, 0, -1)] if decimal
                  else [float(n) for n in range(MAX_ABSENT, 3, -1)])
    return next(c for c in candidates
                if not check_grounding([str(c)], {"evidence": sorted(evidence)}).grounded)


def test_threat_template_outputs_and_every_persona_card_are_grounded(threat_context: MomentContext,
                                                                    tracked: TrackedMatch) -> None:
    facts = threat_context.moment.facts
    explanation = explanation_template(threat_context)
    assert str(facts["passer"]) in explanation.headline and str(facts["xt_added"]) in explanation.why_it_matters
    evidence = [threat_context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert explanation_validator(lambda: [threat_context.to_prompt_dict()])(explanation) is None
    commentary = commentary_template(threat_context, explanation)
    assert commentary_validator(lambda: evidence)(commentary) is None and commentary.line.endswith("!")
    for viewer in _viewers(threat_context, tracked):
        card = persona_card_template(threat_context, explanation, viewer)
        assert card_validator(lambda: evidence, viewer.viewer.profile.max_words)(card) is None
        texts = [card.title, card.body, *(c.value for c in card.stat_callouts)]
        assert check_grounding(texts, threat_context.to_prompt_dict()).grounded, viewer.viewer.persona


def test_drafts_citing_absent_xt_or_bypass_numbers_fail_grounding(threat_context: MomentContext) -> None:
    present = collect_evidence_numbers(threat_context.to_prompt_dict())
    xt, bypassed = _absent(present, decimal=True), _absent(present, decimal=False)
    evidence = threat_context.to_prompt_dict()
    assert not check_grounding([f"That pass added {xt} xT."], evidence).grounded
    assert not check_grounding([f"It took {int(bypassed)} opponents out of the game."], evidence).grounded
    cited = f"It added {threat_context.moment.facts['xt_added']} xT"
    assert check_grounding([cited], evidence).grounded


def test_analyst_card_calls_out_xt_added(threat_context: MomentContext) -> None:
    explanation = explanation_template(threat_context)
    card = persona_card_template(threat_context, explanation, ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)))
    assert "xT added" in [c.label for c in card.stat_callouts]


def test_fact_check_prompt_and_analyst_brief_carry_the_xt_facts(threat_context: MomentContext) -> None:
    prompt = fact_check_prompt(threat_context, explanation_template(threat_context), "card", "draft")
    assert "xt_added" in prompt and "opponents_bypassed" in prompt
    assert "xt_added" in ANALYST_INSTRUCTIONS and "lines_broken" in ANALYST_INSTRUCTIONS
    assert "xt_added" in PERSONAS[PersonaKey.ANALYST].stat_focus


def test_threat_kind_has_a_concept_a_label_and_a_reel_title() -> None:
    term, meaning = concept_for(MomentKind.THREAT_CREATED)
    assert term == "Expected threat (xT)" and meaning
    assert KIND_LABELS[MomentKind.THREAT_CREATED.value] == "line-breaking pass"
    assert KIND_TITLES[MomentKind.THREAT_CREATED] == "Line-breaking pass"


def test_moment_and_question_context_expose_xt(threat_context: MomentContext, tracked: TrackedMatch) -> None:
    assert "xt_added" in PLAYER_CONTEXT_KEYS
    assert all("xt_added" in block for block in threat_context.players.values())
    assert all("xt_added" in block for block in threat_context.teams.values())
    prompt = build_question_context(tracked.analyzer).to_prompt_dict()
    leaders = prompt["threat_leaders"]
    assert isinstance(leaders, list) and 0 < len(leaders) <= 3 and all(r["xt_added"] > 0 for r in leaders)
    assert all("xt_added" in block for block in prompt["teams"].values())  # type: ignore[union-attr]
