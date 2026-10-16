"""Deterministic fallback outputs used when a model call fails, times out, or is not grounded.

Templates build every agent schema directly from moment facts, so they are always grounded and always valid.
They guarantee the broadcast never shows an empty overlay, even with no model available.
"""

import re
import zlib
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
from insidegame.analytics.moments import FactValue, MomentKind, moment_intensity
from insidegame.domain.enums import Intensity

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
    "count": "Count", "share_pct": "Share (%)", "window_minutes": "Window (min)",
}
PATTERN_HEADLINES: dict[str, str] = {
    "flank_exposed": "{team} keep getting in behind down {flank_label}",
    "channel_overload": "{team} are loading the {channel}",
    "turnover_zone": "{team} keep winning the ball in {flank_label}",
}
PATTERN_THEMES: dict[str, TacticalTheme] = {
    "flank_exposed": TacticalTheme.CONTROL, "channel_overload": TacticalTheme.CONTROL,
    "turnover_zone": TacticalTheme.PRESSURE_SHIFT,
}
PATTERN_WARNING: str = "The Tactical Scout expects more danger from it until {opponent} find an answer."
PAYOFF_HEADLINE: str = ", just as the Scout flagged at {minute}"
PAYOFF_SENTENCE: str = " The Tactical Scout flagged it at {minute}: {summary}."
SUPERFAN_OWN_PREFIX: str = "Get in! "
SUPERFAN_SETBACK_PREFIX: str = "So close! "
SUPERFAN_RIVAL_PREFIX: str = "Stay strong. "
SETBACK_KINDS: frozenset[MomentKind] = frozenset({MomentKind.BIG_CHANCE_MISSED})
MAX_CALLOUTS: int = 3
EXCITED_OPENERS: dict[MomentKind, tuple[str, ...]] = {
    MomentKind.DISTANCE_THRESHOLD: ("What a ball!", "Look at that range!", "Oh, that is glorious!", "Superb!"),
    MomentKind.DIFFICULT_PASS: ("Oh, that is clever!", "What vision!", "Wonderful pass!", "Oh, lovely!"),
    MomentKind.SPEED_THRESHOLD: ("What a hit!", "Absolutely hammered!", "Oh, that was struck!", "Thunderous!"),
}
CARRY_OPENERS: tuple[str, ...] = ("What a run!", "Still going!", "Look at this!")
HALF: float = 0.5
SPOKEN_METRES = re.compile(r"(\d+(?:\.\d+)?) m\b")
SPOKEN_SPEED = re.compile(r"(\d+(?:\.\d+)?) km/h")

ExplanationParts = tuple[str, str, list[str], TacticalTheme]


def _f(facts: dict[str, FactValue], key: str) -> str:
    return str(facts.get(key, ""))


def _vary(options: tuple[str, ...], c: MomentContext) -> str:
    """Pick a wording deterministically from the moment id, so repeated moment kinds do not read identically."""
    return options[zlib.crc32(c.moment.moment_id.encode()) % len(options)]


def _payoff(facts: dict[str, FactValue]) -> tuple[str, str]:
    """Headline suffix and sentence linking a goal or chance to an earlier Scout flag, or empty strings."""
    if not facts.get("flagged_minute"):
        return "", ""
    minute, summary = _f(facts, "flagged_minute"), _f(facts, "flagged_summary")
    return PAYOFF_HEADLINE.format(minute=minute), PAYOFF_SENTENCE.format(minute=minute, summary=summary)


def _goal(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    phrase = GAME_STATE_PHRASES.get(_f(f, "game_state_change"), "scores")
    suffix, sentence = _payoff(f)
    return (f"{_f(f, 'scorer')} {phrase}{suffix}",
            f"{c.team_name} {phrase}, making it {c.home_name} {c.score_home}-{c.score_away} {c.away_name}. "
            f"The finish came from a chance worth {_f(f, 'xg')} xG.{sentence}",
            [f"xG {_f(f, 'xg')}", f"Distance {_f(f, 'distance_m')} m"], TacticalTheme.CLINICAL_FINISHING)


def _big_chance(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    player = _f(f, "player")
    suffix, sentence = _payoff(f)
    return (_vary((f"Big chance missed by {player}", f"{player} should have scored there",
                   f"A golden chance goes begging for {player}", f"{player} cannot believe that stayed out"), c) + suffix,
            f"A chance worth {_f(f, 'xg')} xG went begging. Chances of this quality usually change the scoreline."
            f"{sentence}",
            [f"xG {_f(f, 'xg')}", f"Distance {_f(f, 'distance_m')} m"], TacticalTheme.MISSED_OPPORTUNITY)


def _great_save(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    keeper, shooter = _f(f, "goalkeeper"), _f(f, "shooter")
    return (_vary((f"{keeper} denies {shooter}", f"What a stop from {keeper}", f"{keeper} keeps {shooter} out",
                   f"{keeper} comes to the rescue"), c),
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
    team = c.team_name
    return (_vary((f"Momentum swings to {team}", f"{team} take control", f"The tide turns towards {team}",
                   f"{team} are on top now"), c),
            f"{c.team_name} now own the last few minutes of threat. The balance of the match has tipped.",
            [f"Momentum {_f(f, 'momentum')}"], TacticalTheme.PRESSURE_SHIFT)


def _chaos(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    return (_vary(("The match turns chaotic", "End to end, and nobody can keep the ball", "It is frantic out there",
                   "A wild spell of broken play"), c),
            f"Possession is changing hands {_f(f, 'turnovers_per_minute')} times per minute. "
            "Neither side can settle, which favours quick transitions over patient build-up.",
            [f"Turnovers per minute {_f(f, 'turnovers_per_minute')}"], TacticalTheme.CHAOS)


def _milestone(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    label = _f(f, "milestone").replace("_", " ")
    return (f"{_f(f, 'player')} reaches a milestone",
            f"{_f(f, 'player')} marks a {label}. It underlines how central they are to this performance.",
            [label], TacticalTheme.MILESTONE)


def _tactical(c: MomentContext) -> ExplanationParts:
    f = c.moment.facts
    pattern = _f(f, "pattern")
    headline = PATTERN_HEADLINES.get(pattern, "{team} have found a pattern").format(
        team=_f(f, "team"), flank_label=_f(f, "flank_label"), channel=_f(f, "channel"))
    return (headline, f"{_f(f, 'summary')}. " + PATTERN_WARNING.format(opponent=_f(f, "opponent")),
            [f"{_f(f, 'count')} of {_f(f, 'total')}", f"Share {_f(f, 'share_pct')}%"],
            PATTERN_THEMES.get(pattern, TacticalTheme.CONTROL))


EXPLAINERS: dict[MomentKind, Callable[[MomentContext], ExplanationParts]] = {
    MomentKind.GOAL: _goal, MomentKind.BIG_CHANCE_MISSED: _big_chance, MomentKind.GREAT_SAVE: _great_save,
    MomentKind.SPEED_THRESHOLD: _speed, MomentKind.DISTANCE_THRESHOLD: _distance,
    MomentKind.DIFFICULT_PASS: _difficult_pass,
    MomentKind.MOMENTUM_SWING: _momentum, MomentKind.CHAOS_SPELL: _chaos, MomentKind.MILESTONE: _milestone,
    MomentKind.TACTICAL_PATTERN: _tactical,
}


def explanation_template(context: MomentContext) -> Explanation:
    """Build a grounded explanation directly from moment facts."""
    headline, why, evidence, theme = EXPLAINERS[context.moment.kind](context)
    return Explanation(headline=headline, why_it_matters=why, evidence=evidence, theme=theme)


def _whole(number: str) -> int:
    """Round half up, as people do when saying a measurement aloud."""
    return int(float(number) + HALF)


def spoken_units(text: str) -> str:
    """Write measurements the way a commentator says them: whole metres and kilometres an hour."""
    text = SPOKEN_METRES.sub(lambda m: f"{_whole(m.group(1))} metres", text)
    return SPOKEN_SPEED.sub(lambda m: f"{_whole(m.group(1))} kilometres an hour", text)


def _opener(context: MomentContext) -> str:
    """An exclamation that opens a raised line, so bold passes, runs, and rockets get an audible reaction."""
    kind = context.moment.kind
    if kind is MomentKind.DISTANCE_THRESHOLD and context.moment.facts.get("indicator") != "long_pass":
        return _vary(CARRY_OPENERS, context) + " "
    options = EXCITED_OPENERS.get(kind)
    return _vary(options, context) + " " if options else ""


def commentary_template(context: MomentContext, explanation: Explanation) -> Commentary:
    """Build a commentary line from the explanation headline, with punctuation and openers matching its energy.

    Goals are already shouted by the play-by-play, so the moment line reacts ("... breaks the deadlock!") rather
    than repeating "GOAL!". Measurements are written as spoken words because the line is read aloud.
    """
    headline = spoken_units(explanation.headline.rstrip(".!"))
    if moment_intensity(context.moment.kind) is Intensity.NORMAL:
        return Commentary(line=f"{headline}.")
    return Commentary(line=f"{_opener(context)}{headline}!")


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
    MomentKind.MILESTONE.value: "milestone", MomentKind.TACTICAL_PATTERN.value: "Tactical Scout flag",
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
