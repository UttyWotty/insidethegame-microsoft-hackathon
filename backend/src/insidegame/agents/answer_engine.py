"""Deterministic, grounded answers to common viewer questions, voiced for each persona.

It recognises a few question intents (best player, who is on top, momentum, a named player, the score) and answers
from live statistics, so viewers get a real answer when no model is available or a model answer is rejected.
"""

import re
from collections.abc import Callable
from enum import StrEnum

from insidegame.agents.context import ViewerContext
from insidegame.agents.personas import PersonaKey
from insidegame.agents.question_context import QuestionContext
from insidegame.agents.schemas import CompanionAnswer, StatCallout

MAX_CALLOUTS: int = 3
FOLLOW_UPS: dict[str, tuple[str, ...]] = {
    "best_player": ("Which team is on top right now?", "Why has the momentum changed?"),
    "on_top": ("Who has been the best player so far?", "Why has the momentum changed?"),
    "momentum": ("Which team is on top right now?", "Who has been the best player so far?"),
    "player": ("Who has been the best player so far?", "Which team is on top right now?"),
    "score": ("Who has been the best player so far?", "Which team is on top right now?"),
}


class Intent(StrEnum):
    """Question types the engine can answer."""

    BEST_PLAYER = "best_player"
    ON_TOP = "on_top"
    MOMENTUM = "momentum"
    PLAYER = "player"
    SCORE = "score"


INTENT_PATTERNS: tuple[tuple[Intent, re.Pattern[str]], ...] = (
    (Intent.BEST_PLAYER, re.compile(r"\b(best|standout|man of the match|influential|star|mvp)\b", re.I)),
    (Intent.MOMENTUM, re.compile(r"\b(momentum|shift|changed|swing|chaos|rhythm)\b", re.I)),
    (Intent.ON_TOP, re.compile(r"\b(on top|control|dominat\w*|winning|better|ahead|who leads)\b", re.I)),
)


def detect_intent(question: str, context: QuestionContext) -> tuple[Intent, str | None]:
    """Return the question's intent and, for player questions, the player's name."""
    named = next((name for name in context.players if name.lower() in question.lower()
                  or name.split()[-1].lower() in question.lower().split()), None)
    if named:
        return Intent.PLAYER, named
    return next((intent for intent, pattern in INTENT_PATTERNS if pattern.search(question)), Intent.SCORE), None


def _plural(count: object, word: str) -> str:
    return f"{count} {word}" if str(count) == "1" else f"{count} {word}s"


def _leader(context: QuestionContext) -> tuple[str, str]:
    home, away = context.teams[context.home_name], context.teams[context.away_name]
    home_edge = float(home["xg"]) - float(away["xg"]) + (float(home["possession_pct"]) - 50) / 100  # type: ignore[arg-type]
    return (context.home_name, context.away_name) if home_edge >= 0 else (context.away_name, context.home_name)


def _best_player(context: QuestionContext) -> tuple[str, list[StatCallout]]:
    best = context.top_players[0]
    text = (f"{best['name']} of {best['team']} has been the most influential so far: {_plural(best['goals'], 'goal')}, "
            f"{_plural(best['passes_completed'], 'completed pass').replace('passs', 'passes')}, and "
            f"{_plural(best['tackles'], 'tackle')}.")
    return text, [StatCallout(label="Passes completed", value=str(best["passes_completed"])),
                  StatCallout(label="xG", value=str(best["xg"]))]


def _on_top(context: QuestionContext) -> tuple[str, list[StatCallout]]:
    leader, other = _leader(context)
    lead, trail = context.teams[leader], context.teams[other]
    text = (f"{leader} are edging it on chances: {lead['xg']} xG to {trail['xg']} for {other}, from "
            f"{_plural(lead['shots'], 'shot')} with {lead['possession_pct']}% of the ball.")
    return text, [StatCallout(label=f"{leader} xG", value=str(lead["xg"])),
                  StatCallout(label=f"{other} xG", value=str(trail["xg"]))]


def _momentum(context: QuestionContext) -> tuple[str, list[StatCallout]]:
    swings = [m for m in context.recent_moments if m["kind"] in ("momentum_swing", "chaos_spell", "goal")]
    state = str(context.rhythm.get("state", "balanced")).replace("_", " ")
    if not swings:
        return f"The game is {state} right now, with no big swing in the last few minutes.", []
    last = swings[-1]
    reason = {"goal": "a goal changed the picture", "chaos_spell": "possession kept changing hands",
              "momentum_swing": "one side started creating far more danger"}[str(last["kind"])]
    return f"At {last['minute']} {reason}, and the game is now {state}.", []


def _player(context: QuestionContext, name: str) -> tuple[str, list[StatCallout]]:
    p = context.players[name]
    text = (f"{name} ({p['team']}): {_plural(p['goals'], 'goal')} from {_plural(p['shots'], 'shot')}, "
            f"{_plural(p['passes_completed'], 'completed pass').replace('passs', 'passes')}, "
            f"{_plural(p['tackles'], 'tackle')}, and {p['carry_distance_m']} m carried with the ball.")
    return text, [StatCallout(label="Passes completed", value=str(p["passes_completed"])),
                  StatCallout(label="Distance carried (m)", value=str(p["carry_distance_m"]))]


def _score(context: QuestionContext) -> tuple[str, list[StatCallout]]:
    home = context.teams[context.home_name]
    return (f"It is {context.scoreline} at {context.clock}, with {context.home_name} on {home['possession_pct']}% "
            "of the ball."), []


def _voice(text: str, intent: Intent, context: QuestionContext, viewer: ViewerContext) -> str:
    persona = viewer.viewer.persona
    if persona is PersonaKey.SUPERFAN and viewer.favourite_team_name:
        return _superfan(text, intent, context, viewer.favourite_team_name)
    if persona is PersonaKey.PLAYER_TRACKER and viewer.tracked_player_name and intent is not Intent.PLAYER:
        mine = context.players.get(viewer.tracked_player_name, {})
        return f"{text} Your player {viewer.tracked_player_name} has {mine.get('passes_completed', 0)} completed passes."
    if persona is PersonaKey.NEWCOMER and "xG" in text:
        return f"{text} (xG, expected goals, measures how good the chances were.)"
    if persona is PersonaKey.CASUAL:
        return text.split(": ")[0].rstrip(".") + "." if ": " in text else text
    return text


def _superfan(text: str, intent: Intent, context: QuestionContext, ours: str) -> str:
    theirs = context.away_name if ours == context.home_name else context.home_name
    us, them = context.teams[ours], context.teams[theirs]
    winning = _leader(context)[0] == ours
    if intent is Intent.ON_TOP:
        if winning:
            return (f"We're on top! {us['xg']} xG to their {them['xg']}, and {us['possession_pct']}% of the ball. "
                    "Keep it going!")
        return (f"They're edging it for now: {them['xg']} xG to our {us['xg']}. Come on, {ours}, we need more!")
    mood = "Get in, we're running this!" if winning else "Come on, we need more!"
    return f"{mood} {text}"


ANSWERERS: dict[Intent, Callable[[QuestionContext], tuple[str, list[StatCallout]]]] = {
    Intent.BEST_PLAYER: _best_player, Intent.ON_TOP: _on_top, Intent.MOMENTUM: _momentum, Intent.SCORE: _score,
}


def rule_based_answer(question: str, context: QuestionContext, viewer: ViewerContext) -> CompanionAnswer:
    """Answer a viewer's question from live statistics, in the viewer's persona voice."""
    intent, name = detect_intent(question, context)
    text, callouts = _player(context, name) if intent is Intent.PLAYER and name else ANSWERERS[intent](context)
    show_callouts = viewer.viewer.persona is not PersonaKey.CASUAL
    return CompanionAnswer(answer=_voice(text, intent, context, viewer),
                           stat_callouts=callouts[:MAX_CALLOUTS] if show_callouts else [],
                           follow_ups=list(FOLLOW_UPS[intent.value]))
