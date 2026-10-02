"""Viewer segments: viewers with identical preferences share one personalization stream.

Segmenting keeps model cost proportional to distinct preferences rather than connected clients.
Segment ids are deterministic so reconnecting clients rejoin the same stream.
"""

import re

from insidegame.agents.personas import DEFAULT_LANGUAGE, PersonaKey, ViewerProfile
from insidegame.core.exceptions import PersonaConfigError

LANGUAGE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
NONE_TOKEN: str = "none"
SUGGESTED_LANGUAGES: dict[str, str] = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "ar": "Arabic",
    "tr": "Turkish", "ja": "Japanese", "hi": "Hindi", "sw": "Swahili",
}


def segment_id(persona: PersonaKey, language: str, team_id: str | None, player_id: str | None) -> str:
    """Deterministic identifier for a combination of viewer preferences."""
    return "-".join((persona.value, language, team_id or NONE_TOKEN, player_id or NONE_TOKEN))


def build_segment_profile(
    persona: str, language: str = DEFAULT_LANGUAGE, team_id: str | None = None, player_id: str | None = None
) -> ViewerProfile:
    """Validate raw preferences and return the segment's viewer profile.

    Defaults: language is DEFAULT_LANGUAGE; team_id and player_id are None (not set).
    """
    try:
        key = PersonaKey(persona)
    except ValueError as exc:
        raise PersonaConfigError(f"Unknown persona {persona!r}") from exc
    if not LANGUAGE_PATTERN.match(language):
        raise PersonaConfigError(f"Invalid language code {language!r}")
    return ViewerProfile(segment_id(key, language, team_id, player_id), key, language, team_id, player_id)
