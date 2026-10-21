"""Pure mapping from the Match Analyst's tactical theme to the studio visual that best backs its explanation.

The analyst agent chooses a theme for every key moment; the studio follows it, so a pressure shift is shown on the
pressing map, chaos on space control, build-up brilliance on the pass network, and finishing on the heat map.
"""

from enum import StrEnum

from insidegame.agents.schemas import TacticalTheme


class StudioVisual(StrEnum):
    """Visuals the studio can draw."""

    HEAT_MAP = "heat_map"
    PRESSING = "pressing"
    PASS_NETWORK = "pass_network"
    SPACE_CONTROL = "space_control"


DEFAULT_VISUAL: StudioVisual = StudioVisual.SPACE_CONTROL
THEME_VISUALS: dict[TacticalTheme, StudioVisual] = {
    TacticalTheme.CONTROL: StudioVisual.PASS_NETWORK, TacticalTheme.CHAOS: StudioVisual.SPACE_CONTROL,
    TacticalTheme.PRESSURE_SHIFT: StudioVisual.PRESSING, TacticalTheme.INDIVIDUAL_BRILLIANCE: StudioVisual.PASS_NETWORK,
    TacticalTheme.CLINICAL_FINISHING: StudioVisual.HEAT_MAP, TacticalTheme.MISSED_OPPORTUNITY: StudioVisual.HEAT_MAP,
    TacticalTheme.GOALKEEPING: StudioVisual.HEAT_MAP, TacticalTheme.MILESTONE: StudioVisual.HEAT_MAP,
}


def visual_for(theme: str | None) -> StudioVisual:
    """The visual for a theme value, or DEFAULT_VISUAL when the theme is missing or unknown."""
    try:
        return THEME_VISUALS[TacticalTheme(theme)] if theme else DEFAULT_VISUAL
    except ValueError:
        return DEFAULT_VISUAL
