"""Fictional club presets and deterministic squad generation for synthetic fixtures.

All club and player names are invented, so no real trademarks or personal data are involved.
Given the same seed, build_fixture always returns an identical MatchMetadata.
"""

import random
from dataclasses import dataclass

from insidegame.core.constants import ATTRIBUTE_MAX, ATTRIBUTE_MIN
from insidegame.core.exceptions import FixtureError
from insidegame.domain.enums import Position
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Player, PlayerAttributes, Team, TeamStyle

DEFAULT_COMPETITION: str = "Inside the Game Synthetic League"
DEFAULT_KICKOFF_UTC: str = "2026-10-24T14:00:00Z"
ATTRIBUTE_SPREAD: float = 0.12

FORMATION: tuple[Position, ...] = (
    (Position.GOALKEEPER,) + (Position.DEFENDER,) * 4 + (Position.MIDFIELDER,) * 3 + (Position.FORWARD,) * 3
)
SHIRT_NUMBERS: tuple[int, ...] = (1, 2, 5, 6, 3, 4, 8, 10, 7, 9, 11)

ATTRIBUTE_PROFILES: dict[Position, PlayerAttributes] = {
    Position.GOALKEEPER: PlayerAttributes(pace=0.35, passing=0.55, finishing=0.05, tackling=0.30),
    Position.DEFENDER: PlayerAttributes(pace=0.60, passing=0.60, finishing=0.25, tackling=0.75),
    Position.MIDFIELDER: PlayerAttributes(pace=0.62, passing=0.75, finishing=0.45, tackling=0.55),
    Position.FORWARD: PlayerAttributes(pace=0.75, passing=0.60, finishing=0.75, tackling=0.30),
}

FIRST_NAMES: tuple[str, ...] = (
    "Aron", "Bastien", "Caio", "Dario", "Emre", "Felix", "Goran", "Hugo", "Idris", "Jonas",
    "Kofi", "Luca", "Mateo", "Niko", "Oskar", "Pavel", "Quinn", "Rafael", "Sami", "Tomas",
    "Umar", "Viktor", "Wes", "Yusuf", "Zane", "Ansel", "Brio", "Cyrus", "Deniz", "Elias",
)
LAST_NAMES: tuple[str, ...] = (
    "Aldana", "Brekke", "Castell", "Dorrance", "Eklund", "Farrow", "Galvao", "Hollis", "Iversen",
    "Jarrow", "Kessler", "Lindqvist", "Marlowe", "Novak", "Okafor", "Pereira", "Quarry", "Rasmus",
    "Soler", "Tavish", "Ulloa", "Varga", "Whitlock", "Yilmaz", "Zarco", "Aubrey", "Baptiste",
    "Corrigan", "Delacroix", "Esposito", "Fennimore", "Garrick", "Halloran", "Ingram", "Juarez", "Kovacic",
    "Lamberti", "Moreau", "Nakamura", "Ostrander", "Pellegrin", "Quintero", "Rocha", "Sorensen", "Thorne",
    "Uddin", "Valcourt", "Wexley", "Yardley", "Zielinski", "Abernethy", "Bellamy", "Cardoso", "Drummond",
    "Ferreira", "Gunnarsson",
)


@dataclass(frozen=True)
class ClubPreset:
    """Static definition of a fictional club."""

    key: str
    name: str
    short_name: str
    venue: str
    style: TeamStyle


CLUB_PRESETS: dict[str, ClubPreset] = {
    preset.key: preset
    for preset in (
        ClubPreset("brookhaven", "Brookhaven FC", "BRK", "Brookhaven Park",
                   TeamStyle(label="possession", directness=0.25, pressing=0.55, risk=0.35)),
        ClubPreset("ironvale", "Ironvale United", "IRV", "The Foundry Ground",
                   TeamStyle(label="direct", directness=0.75, pressing=0.40, risk=0.65)),
        ClubPreset("kestrel_bay", "Kestrel Bay Athletic", "KBA", "Cliffside Arena",
                   TeamStyle(label="high_press", directness=0.50, pressing=0.85, risk=0.50)),
        ClubPreset("silverlake", "Silverlake Rovers", "SLR", "Lakeshore Stadium",
                   TeamStyle(label="counter", directness=0.65, pressing=0.30, risk=0.55)),
    )
}


def _clamp_attribute(value: float) -> float:
    return min(max(value, ATTRIBUTE_MIN), ATTRIBUTE_MAX)


def _draw_attributes(position: Position, rng: random.Random) -> PlayerAttributes:
    base = ATTRIBUTE_PROFILES[position]
    return PlayerAttributes(
        pace=_clamp_attribute(rng.gauss(base.pace, ATTRIBUTE_SPREAD)),
        passing=_clamp_attribute(rng.gauss(base.passing, ATTRIBUTE_SPREAD)),
        finishing=_clamp_attribute(rng.gauss(base.finishing, ATTRIBUTE_SPREAD)),
        tackling=_clamp_attribute(rng.gauss(base.tackling, ATTRIBUTE_SPREAD)),
    )


def _draw_name(rng: random.Random, taken_surnames: set[str]) -> str:
    """Draw a full name whose surname is unique in the fixture, so short names identify one player."""
    surname = rng.choice([name for name in LAST_NAMES if name not in taken_surnames])
    taken_surnames.add(surname)
    return f"{rng.choice(FIRST_NAMES)} {surname}"


def build_team(preset: ClubPreset, rng: random.Random, taken_surnames: set[str]) -> Team:
    """Generate a starting eleven in a 4-3-3 shape for a club preset, avoiding surnames already taken."""
    players = tuple(
        Player(
            player_id=f"{preset.short_name.lower()}-{shirt:02d}",
            name=_draw_name(rng, taken_surnames),
            shirt_number=shirt,
            position=position,
            attributes=_draw_attributes(position, rng),
        )
        for position, shirt in zip(FORMATION, SHIRT_NUMBERS, strict=True)
    )
    return Team(preset.short_name.lower(), preset.name, preset.short_name, players, preset.style)


def build_fixture(home_key: str, away_key: str, seed: int) -> MatchMetadata:
    """Create reproducible fixture metadata for two club preset keys."""
    if home_key == away_key:
        raise FixtureError("A club cannot play itself")
    missing = [key for key in (home_key, away_key) if key not in CLUB_PRESETS]
    if missing:
        raise FixtureError(f"Unknown club presets: {missing}")
    rng = random.Random(seed)
    taken: set[str] = set()
    home_preset, away_preset = CLUB_PRESETS[home_key], CLUB_PRESETS[away_key]
    home = build_team(home_preset, rng, taken)
    away = build_team(away_preset, rng, taken)
    return MatchMetadata(
        match_id=f"{home.team_id}-{away.team_id}-{seed}",
        competition=DEFAULT_COMPETITION,
        venue=home_preset.venue,
        kickoff_utc=DEFAULT_KICKOFF_UTC,
        home=home,
        away=away,
        seed=seed,
    )
