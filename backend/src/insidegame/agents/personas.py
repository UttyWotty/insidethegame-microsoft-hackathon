"""The five viewer personas and the per-viewer profile used to personalize match intelligence.

Each persona has its own voice, vocabulary, length budget, statistical focus, relevance threshold, and overlay style.
ViewerProfile combines a persona with language, favourite club, and favourite player preferences.
"""

from dataclasses import dataclass
from enum import StrEnum

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.core.exceptions import PersonaConfigError

DEFAULT_LANGUAGE: str = "en"
ALWAYS_RELEVANT_KINDS: frozenset[MomentKind] = frozenset({MomentKind.GOAL})


class PersonaKey(StrEnum):
    """Identifier of a persona."""

    ANALYST = "analyst"
    CASUAL = "casual"
    SUPERFAN = "superfan"
    PLAYER_TRACKER = "player_tracker"
    NEWCOMER = "newcomer"


class Perspective(StrEnum):
    """Whose point of view the output takes."""

    NEUTRAL = "neutral"
    PARTISAN = "partisan"
    PLAYER_CENTRIC = "player_centric"


class OverlayStyle(StrEnum):
    """Visual treatment the render stage should use for this persona."""

    STAT_PANEL = "stat_panel"
    LOWER_THIRD = "lower_third"
    HYPE_BANNER = "hype_banner"
    PLAYER_TAG = "player_tag"
    EXPLAINER_CARD = "explainer_card"


@dataclass(frozen=True)
class PersonaProfile:
    """Static characteristics that make each persona a genuinely different experience."""

    key: PersonaKey
    display_name: str
    audience: str
    voice: str
    vocabulary: str
    max_words: int
    min_importance: float
    stat_focus: tuple[str, ...]
    perspective: Perspective
    explains_terms: bool
    overlay_style: OverlayStyle


PERSONAS: dict[PersonaKey, PersonaProfile] = {
    p.key: p
    for p in (
        PersonaProfile(
            PersonaKey.ANALYST, "The Analyst",
            "Data-hungry viewers, coaches, and studio pundits who want the numbers behind the story.",
            "Precise, measured, and evidence-led. Lead with the metric, then the tactical consequence.",
            "Technical football vocabulary is welcome: xG, expected threat (xT), line-breaking passes, progressive "
            "passes, pressing, rest defence.",
            70, 0.30, ("xg", "pass_difficulty", "momentum", "chaos", "possession_pct", "progressive_passes", "xt_added"),
            Perspective.NEUTRAL, False, OverlayStyle.STAT_PANEL),
        PersonaProfile(
            PersonaKey.CASUAL, "The Casual Fan",
            "Viewers who follow the big moments and want the story without homework.",
            "Warm, energetic, and quick. One clear idea per line.",
            "Everyday language only. No jargon, no abbreviations, no decimals.",
            30, 0.60, ("score", "shots"),
            Perspective.NEUTRAL, False, OverlayStyle.LOWER_THIRD),
        PersonaProfile(
            PersonaKey.SUPERFAN, "The Superfan",
            "Devoted supporters of one club who live every moment through their team's eyes.",
            "Passionate and one-eyed. Speak as a supporter using we and us for the favourite club.",
            "Terrace language and club pride, kept respectful toward opponents.",
            40, 0.45, ("score", "possession_pct", "shots"),
            Perspective.PARTISAN, False, OverlayStyle.HYPE_BANNER),
        PersonaProfile(
            PersonaKey.PLAYER_TRACKER, "The Player Tracker",
            "Fans and fantasy managers who follow a single player through the whole match.",
            "Focused and personal. Everything is framed around the tracked player's involvement.",
            "Player performance language: touches, passes completed, shot speed, distance carried.",
            45, 0.80, ("passes_completed", "pass_accuracy", "shots", "xg", "carry_distance_m", "max_shot_speed_kmh"),
            Perspective.PLAYER_CENTRIC, False, OverlayStyle.PLAYER_TAG),
        PersonaProfile(
            PersonaKey.NEWCOMER, "The Newcomer",
            "People new to football, younger viewers, and new markets learning the game.",
            "Friendly and patient, like a good teacher. Explain one football idea per moment.",
            "Simple words. When a term appears, explain it in a short clause.",
            55, 0.55, ("score", "xg"),
            Perspective.NEUTRAL, True, OverlayStyle.EXPLAINER_CARD),
    )
}


@dataclass(frozen=True)
class ViewerProfile:
    """One viewer's personalization settings.

    Defaults: language is DEFAULT_LANGUAGE; favourite club and player are None (not set).
    """

    viewer_id: str
    persona: PersonaKey
    language: str = DEFAULT_LANGUAGE
    favourite_team_id: str | None = None
    favourite_player_id: str | None = None

    def __post_init__(self) -> None:
        if self.persona is PersonaKey.SUPERFAN and not self.favourite_team_id:
            raise PersonaConfigError("The superfan persona requires a favourite club")
        if self.persona is PersonaKey.PLAYER_TRACKER and not self.favourite_player_id:
            raise PersonaConfigError("The player tracker persona requires a favourite player")

    @property
    def profile(self) -> PersonaProfile:
        """Static persona characteristics for this viewer."""
        return PERSONAS[self.persona]


def is_relevant(moment: KeyMoment, viewer: ViewerProfile) -> bool:
    """Decide whether a key moment should reach this viewer."""
    profile = viewer.profile
    if viewer.persona is PersonaKey.PLAYER_TRACKER and viewer.favourite_player_id in moment.player_ids:
        return True
    if moment.kind in ALWAYS_RELEVANT_KINDS:
        return True
    if viewer.persona is PersonaKey.SUPERFAN and moment.team_id not in (viewer.favourite_team_id, None):
        return False
    return moment.importance >= profile.min_importance
