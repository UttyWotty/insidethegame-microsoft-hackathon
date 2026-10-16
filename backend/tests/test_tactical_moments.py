"""Tests for tactical_pattern key moments and the payoff facts on the goals and chances that fulfil them.

They run the demo match through MatchAnalyzer and check fact keys, snapshot exposure, and flag-to-goal links.
They also check that every fallback output for a linked goal cites the flagged minute and stays grounded.
"""

from dataclasses import dataclass

import pytest

from insidegame.agents.context import MomentContext, ViewerContext, build_moment_context
from insidegame.agents.glossary import concept_for
from insidegame.agents.grounding import check_grounding, collect_evidence_numbers
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.prompts import fact_check_prompt
from insidegame.agents.templates import commentary_template, explanation_template, persona_card_template
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.detectors import TACTICAL_IMPORTANCE
from insidegame.analytics.moments import KeyMoment, MomentKind, moment_intensity
from insidegame.analytics.pattern_rules import PATTERN_WINDOW_S, PatternKind, TacticalPattern
from insidegame.analytics.tactical_facts import tactical_evidence
from insidegame.core.zones import Channel, Third
from insidegame.domain.enums import Intensity
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED, build_fixture

TACTICAL_FACT_KEYS: frozenset[str] = frozenset({
    "pattern", "team", "opponent", "channel", "third", "count", "total", "share_pct", "window_minutes", "defender",
    "flank_label", "summary",
})
FLAGGED_KEYS: frozenset[str] = frozenset({"flagged_minute", "flagged_moment_id", "flagged_pattern", "flagged_summary"})
MAX_MINUTE = 90


@dataclass(frozen=True)
class AnalysedDemo:
    analyzer: MatchAnalyzer
    contexts: dict[str, MomentContext]


@pytest.fixture(scope="module")
def demo() -> AnalysedDemo:
    result = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, DEMO_SEED))
    analyzer = MatchAnalyzer(result.metadata)
    contexts: dict[str, MomentContext] = {}
    for event in result.events:
        for moment in analyzer.ingest(event).moments:
            contexts[moment.moment_id] = build_moment_context(moment, analyzer)
    return AnalysedDemo(analyzer, contexts)


def _viewers(analyzer: MatchAnalyzer) -> list[ViewerContext]:
    home = analyzer.metadata.home
    tracked = home.players[-1]
    return [ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)), ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),
            ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=home.team_id), home.name),
            ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=tracked.player_id),
                          tracked_player_name=tracked.name),
            ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER))]


def _linked_goal(demo: AnalysedDemo) -> MomentContext:
    return next(c for c in demo.contexts.values()
                if c.moment.kind is MomentKind.GOAL and "flagged_minute" in c.moment.facts)


def test_tactical_moments_carry_exactly_the_documented_facts(demo: AnalysedDemo) -> None:
    tactical = [m for m in demo.analyzer.moments if m.kind is MomentKind.TACTICAL_PATTERN]
    assert tactical
    for moment in tactical:
        assert set(moment.facts) == TACTICAL_FACT_KEYS
        assert moment.importance == TACTICAL_IMPORTANCE and moment.team_id is not None
        assert all(isinstance(v, (str, int, float, bool)) or v is None for v in moment.facts.values())
        assert isinstance(moment.facts["share_pct"], int) and isinstance(moment.facts["window_minutes"], int)
        assert (moment.facts["defender"] is None) == (moment.facts["pattern"] != PatternKind.FLANK_EXPOSED.value)
    assert moment_intensity(MomentKind.TACTICAL_PATTERN) is Intensity.NORMAL


def test_tactical_moments_reach_the_snapshot(demo: AnalysedDemo) -> None:
    snapshot_kinds = [m["kind"] for m in demo.analyzer.snapshot()["moments"]]  # type: ignore[union-attr]
    assert MomentKind.TACTICAL_PATTERN.value in snapshot_kinds


def test_linked_moments_point_to_an_earlier_flag(demo: AnalysedDemo) -> None:
    by_id = {m.moment_id: m for m in demo.analyzer.moments}
    linked = [m for m in demo.analyzer.moments if "flagged_minute" in m.facts]
    assert any(m.kind is MomentKind.GOAL for m in linked)
    for moment in linked:
        assert moment.kind in (MomentKind.GOAL, MomentKind.BIG_CHANCE_MISSED)
        assert FLAGGED_KEYS <= set(moment.facts)
        flag = by_id[str(moment.facts["flagged_moment_id"])]
        assert flag.kind is MomentKind.TACTICAL_PATTERN and flag.team_id == moment.team_id
        assert (flag.period, flag.match_second) < (moment.period, moment.match_second)
        assert moment.facts["flagged_minute"] == flag.minute_label
        assert moment.facts["flagged_summary"] == flag.facts["summary"]
        assert moment.facts["flagged_pattern"] == flag.facts["pattern"]


def test_unlinked_goals_have_no_flagged_facts(demo: AnalysedDemo) -> None:
    unlinked = [m for m in demo.analyzer.moments if m.kind is MomentKind.GOAL and "flagged_minute" not in m.facts]
    assert unlinked
    assert all(not FLAGGED_KEYS & set(m.facts) for m in unlinked)


def test_linked_goal_outputs_cite_the_flagged_minute_and_stay_grounded(demo: AnalysedDemo) -> None:
    context = _linked_goal(demo)
    minute = str(context.moment.facts["flagged_minute"])
    explanation = explanation_template(context)
    evidence = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert minute in explanation.headline and minute in explanation.why_it_matters
    assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None
    line = commentary_template(context, explanation).line
    assert minute in line and commentary_validator(lambda: evidence)(commentary_template(context, explanation)) is None
    for viewer in _viewers(demo.analyzer):
        card = persona_card_template(context, explanation, viewer)
        assert minute in f"{card.title} {card.body}", viewer.viewer.persona
        assert card_validator(lambda: evidence, viewer.viewer.profile.max_words)(card) is None
        assert check_grounding([card.title, card.body], context.to_prompt_dict()).grounded


def test_a_draft_citing_an_absent_minute_fails_grounding(demo: AnalysedDemo) -> None:
    context = _linked_goal(demo)
    present = collect_evidence_numbers(context.to_prompt_dict())
    absent = next(m for m in range(MAX_MINUTE, 0, -1) if all(abs(m - n) > 1 for n in present))
    draft = f"The Tactical Scout warned about this at {absent}'."
    assert not check_grounding([draft], context.to_prompt_dict()).grounded


def test_fact_check_prompt_carries_the_payoff(demo: AnalysedDemo) -> None:
    context = _linked_goal(demo)
    prompt = fact_check_prompt(context, explanation_template(context), "card", "draft")
    assert "flagged_minute" in prompt and "flagged_summary" in prompt


@pytest.mark.parametrize(("kind", "channel", "third"), [
    (PatternKind.FLANK_EXPOSED, Channel.LEFT, Third.FINAL),
    (PatternKind.CHANNEL_OVERLOAD, Channel.CENTRE, Third.FINAL),
    (PatternKind.TURNOVER_ZONE, Channel.RIGHT, Third.MIDDLE),
])
def test_tactical_template_is_grounded_for_every_pattern_kind(
    demo: AnalysedDemo, kind: PatternKind, channel: Channel, third: Third,
) -> None:
    analyzer = demo.analyzer
    home, away = analyzer.metadata.home.team_id, analyzer.metadata.away.team_id
    pattern = TacticalPattern(kind, home, away, channel, third, 7, 9, PATTERN_WINDOW_S)
    evidence = tactical_evidence(pattern, analyzer.metadata)
    moment = KeyMoment("t-1", MomentKind.TACTICAL_PATTERN, 1, 1200.0, TACTICAL_IMPORTANCE, home,
                       evidence.player_ids, (), evidence.facts)
    context = build_moment_context(moment, analyzer)
    explanation = explanation_template(context)
    outputs = [context.to_prompt_dict(), explanation.model_dump(mode="json")]
    assert explanation_validator(lambda: [context.to_prompt_dict()])(explanation) is None
    assert str(evidence.facts["summary"]) in explanation.why_it_matters
    assert commentary_validator(lambda: outputs)(commentary_template(context, explanation)) is None
    for viewer in _viewers(analyzer):
        card = persona_card_template(context, explanation, viewer)
        assert card_validator(lambda: outputs, viewer.viewer.profile.max_words)(card) is None
    assert concept_for(MomentKind.TACTICAL_PATTERN)[0]


INVARIANT_CLUBS: tuple[str, ...] = ("brookhaven", "ironvale", "kestrel_bay", "silverlake")
INVARIANT_SEEDS: range = range(1, 4)
MIN_FLAG_GAP_S = 600.0
PAYOFF_LIMIT_S = 900.0


@pytest.mark.parametrize("home,away", [(h, a) for h in INVARIANT_CLUBS for a in INVARIANT_CLUBS if h != a])
def test_flags_and_links_hold_their_invariants_for_every_pairing(home: str, away: str) -> None:
    for seed in INVARIANT_SEEDS:
        result = simulate_match(build_fixture(home, away, seed))
        analyzer = MatchAnalyzer(result.metadata)
        for event in result.events:
            analyzer.ingest(event)
        by_id = {m.moment_id: m for m in analyzer.moments}
        flags = [m for m in analyzer.moments if m.kind is MomentKind.TACTICAL_PATTERN]
        for flag in flags:
            assert set(flag.facts) == TACTICAL_FACT_KEYS
            assert (flag.facts["pattern"] != PatternKind.FLANK_EXPOSED.value) or (flag.player_ids and flag.facts["defender"])
        for period in {f.period for f in flags}:
            seconds = sorted(f.match_second for f in flags if f.period == period)
            assert all(b - a >= MIN_FLAG_GAP_S for a, b in zip(seconds, seconds[1:]))
        for moment in analyzer.moments:
            keys = {k for k in moment.facts if k.startswith("flagged_")}
            if not keys:
                continue
            assert moment.kind in (MomentKind.GOAL, MomentKind.BIG_CHANCE_MISSED) and keys == FLAGGED_KEYS
            flag = by_id[str(moment.facts["flagged_moment_id"])]
            assert flag.kind is MomentKind.TACTICAL_PATTERN and flag.minute_label == moment.facts["flagged_minute"]
            assert (flag.period, flag.team_id) == (moment.period, moment.team_id)
            assert 0 < moment.match_second - flag.match_second <= PAYOFF_LIMIT_S
