"""Viewer segments: viewers with identical preferences share one personalization stream.

Segmenting keeps model cost proportional to distinct preferences rather than connected clients.
Segment ids are deterministic so reconnecting clients rejoin the same stream.
"""

import re

from insidegame.agents.personas import DEFAULT_LANGUAGE, PersonaKey, ViewerProfile
from insidegame.core.exceptions import PersonaConfigError
from insidegame.domain.match import MatchMetadata

LANGUAGE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
NONE_TOKEN: str = "none"
SUGGESTED_LANGUAGES: dict[str, str] = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "ar": "Arabic",
    "tr": "Turkish", "ja": "Japanese", "hi": "Hindi", "sw": "Swahili",
}


def segment_id(persona: PersonaKey, language: str, team_id: str | None, player_id: str | None) -> str:
    """Deterministic identifier for a combination of viewer preferences."""
    return "-".join((persona.value, language, team_id or NONE_TOKEN, player_id or NONE_TOKEN))


def parse_persona(persona: str) -> PersonaKey:
    """Return the persona key, raising PersonaConfigError for unknown names."""
    try:
        return PersonaKey(persona)
    except ValueError as exc:
        raise PersonaConfigError(f"Unknown persona {persona!r}") from exc


def build_segment_profile(
    persona: str, language: str = DEFAULT_LANGUAGE, team_id: str | None = None, player_id: str | None = None
) -> ViewerProfile:
    """Validate raw preferences and return the segment's viewer profile.

    Defaults: language is DEFAULT_LANGUAGE; team_id and player_id are None (not set).
    """
    key = parse_persona(persona)
    if not LANGUAGE_PATTERN.match(language):
        raise PersonaConfigError(f"Invalid language code {language!r}")
    return ViewerProfile(segment_id(key, language, team_id, player_id), key, language, team_id, player_id)


def fixture_segment_profile(
    metadata: MatchMetadata, persona: str, language: str = DEFAULT_LANGUAGE, team_id: str | None = None,
    player_id: str | None = None,
) -> ViewerProfile:
    """Build a segment profile validated against the fixture, dropping preferences the persona does not use.

    Defaults: language is DEFAULT_LANGUAGE; team_id and player_id are None (not set).
    """
    key = parse_persona(persona)
    team = team_id if key is PersonaKey.SUPERFAN else None
    player = player_id if key is PersonaKey.PLAYER_TRACKER else None
    if team is not None and team not in (metadata.home.team_id, metadata.away.team_id):
        raise PersonaConfigError(f"Unknown club {team!r} for this match")
    players = {p.player_id for t in (metadata.home, metadata.away) for p in t.players}
    if player is not None and player not in players:
        raise PersonaConfigError(f"Unknown player {player!r} for this match")
    return build_segment_profile(persona, language, team, player)
