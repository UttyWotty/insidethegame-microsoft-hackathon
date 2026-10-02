"""Deterministic fallback outputs used when a model call fails, times out, or is not grounded.

Templates build every agent schema directly from moment facts, so they are always grounded and always valid.
They guarantee the broadcast never shows an empty overlay, even with no model available.
"""

from collections.abc import Callable

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.glossary import concept_for
from insidegame.agents.personas import PersonaKey
from insidegame.agents.recap_context import RecapContext, RecapStage, moment_actor
from insidegame.agents.schemas import (
    Commentary,
    Explanation,
    MatchRecap,
    PersonaCard,
    StatCallout,
    TacticalTheme,
    TranslatedCard,
)
from insidegame.analytics.moments import FactValue, MomentKind

GAME_STATE_PHRASES: dict[str, str] = {
    "opener": "breaks the deadlock",
    "equaliser": "levels the match",
    "go_ahead": "puts their side in front",
    "extends_lead": "extends the lead",
    "pulls_one_back": "pulls one back",
}
FACT_LABELS: dict[str, str] = {
    "xg": "xG", "xg_prevented": "xG prevented", "shot_speed_kmh": "Shot speed (km/h)",
    "distance_m": "Distance (m)", "difficulty": "Pass difficulty", "length_m": "Pass length (m)",
    "momentum": "Momentum", "turnovers_per_minute": "Turnovers per min",
    "carry_distance_m": "Distance carried (m)", "ball_speed_kmh": "Ball speed (km/h)",
}
SUPERFAN_OWN_PREFIX: str = "Get in! "
SUPERFAN_SETBACK_PREFIX: str = "So close! "
SUPERFAN_RIVAL_PREFIX: str = "Stay strong. "
SETBACK_KINDS: frozenset[MomentKind] = frozenset({MomentKind.BIG_CHANCE_MISSED})
MAX_CALLOUTS: int = 3

ExplanationParts = tuple[str, str, list[str], TacticalTheme]


def _f(facts: dict[str, FactValue], key: str) -> str:
    return str(facts.get(key, ""))


def _goal(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    phrase = GAME_STATE_PHRASES.get(_f(f, "game_state_change"), "scores")
    return (f"{_f(f, 'scorer')} {phrase}",
            f"{c.team_name} {phrase}, making it {c.home_name} {c.score_home}-{c.score_away} {c.away_name}. "
            f"The finish came from a chance worth {_f(f, 'xg')} xG.",
            [f"xG {_f(f, 'xg')}", f"Distance {_f(f, 'distance_m')} m"], TacticalTheme.CLINICAL_FINISHING)


def _big_chance(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (f"Big chance missed by {_f(f, 'player')}",
            f"A chance worth {_f(f, 'xg')} xG went begging. Chances of this quality usually change the scoreline.",
            [f"xG {_f(f, 'xg')}", f"Distance {_f(f, 'distance_m')} m"], TacticalTheme.MISSED_OPPORTUNITY)


def _great_save(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (f"{_f(f, 'goalkeeper')} denies {_f(f, 'shooter')}",
            f"The save prevented {_f(f, 'xg_prevented')} expected goals. It keeps the score at "
            f"{c.score_home}-{c.score_away}.", [f"xG prevented {_f(f, 'xg_prevented')}"], TacticalTheme.GOALKEEPING)


def _speed(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (f"{_f(f, 'player')} strikes at {_f(f, 'shot_speed_kmh')} km/h",
            "Shots this fast leave the goalkeeper almost no reaction time. It is a sign of growing attacking intent.",
            [f"Shot speed {_f(f, 'shot_speed_kmh')} km/h"], TacticalTheme.INDIVIDUAL_BRILLIANCE)


def _distance(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    if f.get("indicator") == "long_pass":
        return (f"{_f(f, 'passer')} finds {_f(f, 'receiver')} from {_f(f, 'length_m')} m",
                "A completed pass this long moves the ball past whole lines of defenders in one action. "
                "It lets the team attack before the opponent can reorganise.",
                [f"Length {_f(f, 'length_m')} m", f"Ball speed {_f(f, 'ball_speed_kmh')} km/h"],
                TacticalTheme.INDIVIDUAL_BRILLIANCE)
    threshold = int(float(f.get("threshold_m") or 0))
    return (f"{_f(f, 'player')} tops {threshold} m carried with the ball",
            f"{_f(f, 'player')} has now carried the ball {_f(f, 'carry_distance_m')} m. "
            "Players who drive forward with the ball are carrying their team's attack.",
            [f"Distance carried {_f(f, 'carry_distance_m')} m"], TacticalTheme.INDIVIDUAL_BRILLIANCE)


def _difficult_pass(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (f"{_f(f, 'passer')} finds {_f(f, 'receiver')}",
            f"A pass rated {_f(f, 'difficulty')} for difficulty unlocked the defence. "
            "Completing passes like this breaks pressure and moves the play into dangerous areas.",
            [f"Difficulty {_f(f, 'difficulty')}", f"Length {_f(f, 'length_m')} m"], TacticalTheme.INDIVIDUAL_BRILLIANCE)


def _momentum(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (f"Momentum swings to {c.team_name}",
            f"{c.team_name} now own the last few minutes of threat. The balance of the match has tipped.",
            [f"Momentum {_f(f, 'momentum')}"], TacticalTheme.PRESSURE_SHIFT)


def _chaos(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return ("The match turns chaotic",
            f"Possession is changing hands {_f(f, 'turnovers_per_minute')} times per minute. "
            "Neither side can settle, which favours quick transitions over patient build-up.",
            [f"Turnovers per minute {_f(f, 'turnovers_per_minute')}"], TacticalTheme.CHAOS)


def _milestone(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    label = _f(f, "milestone").replace("_", " ")
    return (f"{_f(f, 'player')} reaches a milestone",
            f"{_f(f, 'player')} marks a {label}. It underlines how central they are to this performance.",
            [label], TacticalTheme.MILESTONE)


EXPLAINERS: dict[MomentKind, Callable[[MomentContext], ExplanationParts]] = {
    MomentKind.GOAL: _goal, MomentKind.BIG_CHANCE_MISSED: _big_chance, MomentKind.GREAT_SAVE: _great_save,
    MomentKind.SPEED_THRESHOLD: _speed, MomentKind.DISTANCE_THRESHOLD: _distance,
    MomentKind.DIFFICULT_PASS: _difficult_pass,
    MomentKind.MOMENTUM_SWING: _momentum, MomentKind.CHAOS_SPELL: _chaos, MomentKind.MILESTONE: _milestone,
}


def explanation_template(context: MomentContext) -> Explanation:
    """Build a grounded explanation directly from moment facts."""
    headline, why, evidence, theme = EXPLAINERS[context.moment.kind](context)
    return Explanation(headline=headline, why_it_matters=why, evidence=evidence, theme=theme)


def commentary_template(context: MomentContext, explanation: Explanation) -> Commentary:
    """Build a commentary line from the explanation headline."""
    return Commentary(line=f"{explanation.headline.rstrip('.')}.")


def _callouts(context: MomentContext) -> list[StatCallout]:
    facts = context.moment.facts
    return [StatCallout(label=label, value=str(facts[key])) for key, label in FACT_LABELS.items()
            if key in facts][:MAX_CALLOUTS]


def _superfan_prefix(context: MomentContext, viewer: ViewerContext) -> str:
    if context.team_name != viewer.favourite_team_name:
        return SUPERFAN_RIVAL_PREFIX
    return SUPERFAN_SETBACK_PREFIX if context.moment.kind in SETBACK_KINDS else SUPERFAN_OWN_PREFIX


def persona_card_template(context: MomentContext, explanation: Explanation, viewer: ViewerContext) -> PersonaCard:
    """Build a persona-specific card from the explanation without any model call."""
    persona = viewer.viewer.persona
    title, body, callouts = explanation.headline, explanation.why_it_matters, _callouts(context)
    if persona is PersonaKey.CASUAL:
        body, callouts = f"{explanation.headline}. It is {context.score_home}-{context.score_away}.", []
    elif persona is PersonaKey.SUPERFAN:
        body = _superfan_prefix(context, viewer) + explanation.why_it_matters
    elif persona is PersonaKey.PLAYER_TRACKER and viewer.tracked_player_name:
        stats = context.players.get(viewer.tracked_player_name, {})
        title = f"Tracking {viewer.tracked_player_name}"
        callouts = [StatCallout(label=k.replace("_", " ").capitalize(), value=str(v))
                    for k, v in stats.items()][:MAX_CALLOUTS]
    elif persona is PersonaKey.NEWCOMER:
        term, meaning = concept_for(context.moment.kind)
        body = f"{explanation.headline.rstrip('.')}. {term}: {meaning}"
    return PersonaCard(title=title, body=body, stat_callouts=callouts)


def untranslated_card(card: PersonaCard) -> TranslatedCard:
    """Fallback translation that keeps the original English text."""
    return TranslatedCard(title=card.title, body=card.body, stat_labels=[c.label for c in card.stat_callouts])


KIND_LABELS: dict[str, str] = {
    MomentKind.GOAL.value: "goal", MomentKind.BIG_CHANCE_MISSED.value: "big chance missed",
    MomentKind.GREAT_SAVE.value: "great save", MomentKind.SPEED_THRESHOLD.value: "thunderous strike",
    MomentKind.DISTANCE_THRESHOLD.value: "long-range play", MomentKind.DIFFICULT_PASS.value: "defence-splitting pass",
    MomentKind.MOMENTUM_SWING.value: "momentum swing", MomentKind.CHAOS_SPELL.value: "chaotic spell",
    MomentKind.MILESTONE.value: "milestone",
}


def _turning_point(moment: dict[str, object]) -> str:
    facts = moment.get("facts")
    actor = moment_actor(facts) if isinstance(facts, dict) else None
    label = KIND_LABELS.get(str(moment["kind"]), str(moment["kind"]).replace("_", " "))
    return f"{moment['minute']} {label}" + (f": {actor}" if actor else f": {moment.get('team') or 'both sides'}")


def recap_template(context: RecapContext) -> MatchRecap:
    """Build a grounded recap directly from recap evidence."""
    home, away = context.teams[context.home_name], context.teams[context.away_name]
    stage = "Half-time" if context.stage is RecapStage.HALF_TIME else "Full-time"
    scoreline = f"{context.home_name} {context.score_home}-{context.score_away} {context.away_name}"
    summary = (f"{stage}: {scoreline}. {context.home_name} had {home['possession_pct']}% of the ball and "
               f"{home['shots']} shots, while {context.away_name} managed {away['shots']}. "
               f"{context.standout['name']} was the most influential player on the pitch.")
    story = (f"{context.home_name} generated {home['xg']} xG against {away['xg']} for {context.away_name}, "
             "which shaped how the match was controlled.")
    return MatchRecap(headline=f"{stage}: {scoreline}", summary=summary,
                      turning_points=[_turning_point(m) for m in context.moments],
                      standout_player=str(context.standout["name"]), tactical_story=story)
