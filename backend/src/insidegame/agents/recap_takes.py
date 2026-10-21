"""Deterministic persona takes on a recap, used when no model take is available.

Each persona reads the same half-time or full-time facts differently: tactics, a quick summary, a supporter's mood,
one player's match, or a short lesson. Every number comes from the recap context, so takes are always grounded.
"""

from insidegame.agents.context import ViewerContext
from insidegame.agents.personas import PersonaKey
from insidegame.agents.recap_context import RecapContext
from insidegame.agents.schemas import RecapTake
from insidegame.analytics.recap_basis import RecapStage

STAGE_NAMES: dict[RecapStage, str] = {RecapStage.HALF_TIME: "half-time", RecapStage.FULL_TIME: "full-time"}


def _analyst(c: RecapContext, stage: str) -> RecapTake:
    h, a = c.teams[c.home_name], c.teams[c.away_name]
    return RecapTake(headline=f"The numbers at {stage}",
                     take=f"{c.home_name}: {h['possession_pct']}% possession, {h['shots']} shots, {h['xg']} xG. "
                          f"{c.away_name}: {a['shots']} shots, {a['xg']} xG. {c.standout['name']} leads on impact.")


def _casual(c: RecapContext, stage: str) -> RecapTake:
    return RecapTake(headline=f"{c.home_name} {c.score_home}-{c.score_away} {c.away_name}",
                     take=f"That's {stage}. Keep an eye on {c.standout['name']}.")


def _superfan(c: RecapContext, stage: str, team: str | None) -> RecapTake:
    ours = team or c.home_name
    is_home = ours == c.home_name
    us, them = (c.score_home, c.score_away) if is_home else (c.score_away, c.score_home)
    mood = "We're winning" if us > them else "All square" if us == them else "We're behind"
    stats = c.teams[ours]
    return RecapTake(headline=f"{mood} at {stage}!",
                     take=f"{mood}, {us}-{them}. We've had {stats['possession_pct']}% of the ball and {stats['shots']} "
                          "shots. Come on!")


def _tracker(c: RecapContext, stage: str, player: str | None) -> RecapTake:
    stats = c.players.get(player or "", {})
    if not stats:
        return _casual(c, stage)
    return RecapTake(headline=f"{player} at {stage}",
                     take=f"{player}: {stats['goals']} goals from {stats['shots']} shots, {stats['passes_completed']} "
                          f"completed passes, and {stats['tackles']} tackles.")


def _newcomer(c: RecapContext, stage: str) -> RecapTake:
    h, a = c.teams[c.home_name], c.teams[c.away_name]
    return RecapTake(headline=f"What happened by {stage}",
                     take=f"It is {c.home_name} {c.score_home}-{c.score_away} {c.away_name}. Expected goals (xG) adds up "
                          f"how good each chance was: {h['xg']} for {c.home_name} and {a['xg']} for {c.away_name}.")


def template_take(context: RecapContext, viewer: ViewerContext) -> RecapTake:
    """Return the persona's grounded take on the recap without any model call."""
    stage = STAGE_NAMES[context.stage]
    persona = viewer.viewer.persona
    if persona is PersonaKey.ANALYST:
        return _analyst(context, stage)
    if persona is PersonaKey.SUPERFAN:
        return _superfan(context, stage, viewer.favourite_team_name)
    if persona is PersonaKey.PLAYER_TRACKER:
        return _tracker(context, stage, viewer.tracked_player_name)
    if persona is PersonaKey.NEWCOMER:
        return _newcomer(context, stage)
    return _casual(context, stage)
