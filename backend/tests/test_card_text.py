"""Tests for fitting persona card bodies into the persona word budget, and for template cards on long Scout goals.

The pure helper is checked for unchanged fits, whole-sentence trimming, word-boundary truncation, and the prefix.
Seeds whose flagged goals once produced over-budget superfan cards are replayed to prove every card now passes.
"""

import pytest

from insidegame.agents.card_text import TRUNCATION_MARK, fit_card_body, word_budget
from insidegame.agents.context import ViewerContext, build_moment_context, build_viewer_context
from insidegame.agents.grounding import check_grounding
from insidegame.agents.personas import PERSONAS, PersonaKey, ViewerProfile
from insidegame.agents.schemas import PersonaCard
from insidegame.agents.templates import (
    SUPERFAN_OWN_PREFIX,
    SUPERFAN_RIVAL_PREFIX,
    SUPERFAN_SETBACK_PREFIX,
    explanation_template,
    persona_card_template,
)
from insidegame.agents.validation import card_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.core.exceptions import CardBudgetError
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, TrackingModel

SMALL_BUDGET = 10
PREFIX = "Get in! "
ONCE_OVER_BUDGET_SEEDS = (779, 802, 1176, 1809, 3693)
SCOUT_LINK = "just as the Scout flagged at"
DEMO_SEED = 1407
DEMO_ARC_MINUTE = "65'"
DEMO_SUPERFAN_PREFIXES = (SUPERFAN_OWN_PREFIX, SUPERFAN_RIVAL_PREFIX)
DEMO_SUPERFAN_BODY_TAIL = (
    "Kestrel Bay Athletic puts their side in front, making it Kestrel Bay Athletic 2-1 Ironvale United. "
    "The finish came from a chance worth 0.136 xG."
)


def _words(text: str) -> int:
    return len(text.split())


def test_text_that_fits_is_returned_unchanged() -> None:
    text = "Short and sweet. Still short."
    assert fit_card_body(PREFIX, text, SMALL_BUDGET) == PREFIX + text
    assert fit_card_body("", text, SMALL_BUDGET) == text


def test_long_text_keeps_only_the_leading_whole_sentences_that_fit() -> None:
    text = "One two three. Four five six. Seven eight nine ten eleven twelve thirteen."
    fitted = fit_card_body(PREFIX, text, SMALL_BUDGET)
    assert fitted == PREFIX + "One two three. Four five six."
    assert _words(fitted) <= word_budget(SMALL_BUDGET)


def test_decimal_points_are_not_sentence_ends() -> None:
    text = "A chance worth 0.383 xG went in. The Tactical Scout flagged it at 14' and kept on and on about it."
    assert fit_card_body(PREFIX, text, SMALL_BUDGET) == PREFIX + "A chance worth 0.383 xG went in."


def test_single_long_sentence_is_cut_at_a_word_boundary() -> None:
    sentence = "Kestrel Bay Athletic beat Wes Thorne down the right flank: 6 of 7 entries in 15 minutes, again and again."
    fitted = fit_card_body(PREFIX, sentence, SMALL_BUDGET)
    assert fitted.startswith(PREFIX)
    assert fitted.endswith(TRUNCATION_MARK)
    kept = fitted.removeprefix(PREFIX).removesuffix(TRUNCATION_MARK).split()
    assert kept == sentence.split()[:len(kept)]
    assert _words(fitted) == int(word_budget(SMALL_BUDGET))


def test_truncation_drops_dangling_clause_punctuation() -> None:
    words = [f"w{i}" for i in range(int(word_budget(SMALL_BUDGET)))]
    text = " ".join(words) + ", and then the sentence goes on well past the budget."
    assert fit_card_body("", text, SMALL_BUDGET) == " ".join(words) + TRUNCATION_MARK


@pytest.mark.parametrize("persona", list(PersonaKey))
def test_fitted_bodies_never_exceed_any_persona_budget(persona: PersonaKey) -> None:
    max_words = PERSONAS[persona].max_words
    text = " ".join(f"Sentence {i} has exactly six words." for i in range(max_words))
    for prefix in ("", PREFIX):
        fitted = fit_card_body(prefix, text, max_words)
        assert fitted.startswith(prefix)
        assert _words(fitted) <= word_budget(max_words)
        card = PersonaCard(title=persona.value, body=fitted, stat_callouts=[])
        assert card_validator(lambda: [text], max_words)(card) is None


def test_a_prefix_longer_than_the_budget_is_a_domain_error() -> None:
    with pytest.raises(CardBudgetError):
        fit_card_body("word " * SMALL_BUDGET * 2, "text.", SMALL_BUDGET)


def _goal_cards(seed: int) -> list[tuple[str, ViewerContext, object, object]]:
    """Template cards for every goal of a seed, with contexts built at ingest time as the live service does."""
    result = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, seed))
    metadata = result.metadata
    analyzer, tracking = MatchAnalyzer(metadata), TrackingModel(metadata)
    cards = []
    for index, event in enumerate(result.events):
        update = analyzer.ingest(event, tracking.previous or None)
        for moment in (m for m in update.moments if m.kind is MomentKind.GOAL):
            context = build_moment_context(moment, analyzer, tuple(moment.player_ids))
            explanation = explanation_template(context)
            evidence = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
            profiles = [ViewerProfile(p.value, p) for p in (PersonaKey.ANALYST, PersonaKey.CASUAL, PersonaKey.NEWCOMER)]
            profiles += [ViewerProfile(f"s{t.team_id}", PersonaKey.SUPERFAN, favourite_team_id=t.team_id)
                         for t in (metadata.home, metadata.away)]
            profiles += [ViewerProfile(f"t{pid}", PersonaKey.PLAYER_TRACKER, favourite_player_id=pid)
                         for pid in moment.player_ids]
            for profile in profiles:
                viewer = build_viewer_context(profile, metadata)
                cards.append((moment.minute_label, viewer, persona_card_template(context, explanation, viewer),
                              evidence))
        tracking.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
    return cards


@pytest.mark.parametrize("seed", ONCE_OVER_BUDGET_SEEDS)
def test_flagged_goal_cards_fit_and_keep_the_scout_link(seed: int) -> None:
    cards = _goal_cards(seed)
    for minute, viewer, card, evidence in cards:
        max_words = viewer.viewer.profile.max_words
        assert card_validator(lambda: evidence, max_words)(card) is None, (seed, minute, viewer.viewer.viewer_id)
        assert check_grounding([card.title, card.body], evidence).grounded
    superfan = [(v, c) for _, v, c, _ in cards if v.viewer.persona is PersonaKey.SUPERFAN and SCOUT_LINK in c.title]
    assert superfan, seed
    own = [c for v, c in superfan if c.body.startswith(SUPERFAN_OWN_PREFIX)]
    assert own, seed


@pytest.mark.parametrize("prefix", [SUPERFAN_OWN_PREFIX, SUPERFAN_SETBACK_PREFIX, SUPERFAN_RIVAL_PREFIX])
@pytest.mark.parametrize("persona", list(PersonaKey))
def test_every_superfan_prefix_fits_every_persona_budget(prefix: str, persona: PersonaKey) -> None:
    max_words = PERSONAS[persona].max_words
    fitted = fit_card_body(prefix, "One very long sentence " * max_words + "ends here.", max_words)
    assert fitted.startswith(prefix)
    assert _words(fitted) <= word_budget(max_words)


def test_an_empty_body_keeps_only_the_prefix() -> None:
    assert fit_card_body(PREFIX, "", SMALL_BUDGET) == PREFIX
    assert fit_card_body("", "", SMALL_BUDGET) == ""


def test_demo_seed_superfan_goal_card_drops_only_the_trailing_scout_sentence() -> None:
    superfan = [(m, v, c) for m, v, c, _ in _goal_cards(DEMO_SEED)
                if v.viewer.persona is PersonaKey.SUPERFAN and m == DEMO_ARC_MINUTE]
    assert all(SCOUT_LINK in card.title for _, _, card in superfan)
    assert sorted(card.body for _, _, card in superfan) == sorted(p + DEMO_SUPERFAN_BODY_TAIL for p in DEMO_SUPERFAN_PREFIXES)
