"""Assembles the studio payload for a live session: maps, pass networks, space control, shape, and the analyst's pick.

It reads what the session has already played and recorded, filters events to the requested window, and lets the
Match Analyst's latest explanation choose the recommended visual (its own template when no agent card exists yet),
so the pundit screen follows the agent's reasoning.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum

from insidegame.agents.context import MomentContext
from insidegame.agents.runner import OutputSource
from insidegame.agents.templates import explanation_template
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights.reel import FrameRecord
from insidegame.live.producer import BroadcastRecord
from insidegame.studio.control import space_control
from insidegame.studio.maps import DEFENSIVE, ON_BALL, density, pass_network
from insidegame.studio.themes import visual_for

LAST_15_S: float = 900.0


class StudioWindow(StrEnum):
    """Which stretch of the match the studio maps cover."""

    MATCH = "match"
    LAST_15 = "last_15"


def _window(events: Sequence[MatchEvent], window: StudioWindow) -> list[MatchEvent]:
    if window is StudioWindow.MATCH or not events:
        return list(events)
    latest = events[-1].match_second
    return [e for e in events if e.match_second >= latest - LAST_15_S]


def _model_written(record: BroadcastRecord) -> bool:
    """Whether the Match Analyst's explanation for this record came from the model rather than a template."""
    for cue in record.cues:
        provenance = cue.get("provenance")
        entry = provenance.get("explanation") if isinstance(provenance, dict) else None
        if isinstance(entry, dict):
            return entry.get("source") != OutputSource.FALLBACK.value
    return not record.degraded


def _analyst_pick(records: Mapping[str, BroadcastRecord], recent: Sequence[MomentContext]) -> dict[str, object] | None:
    """The newest analyst explanation (agent card first, template for the newest moment otherwise)."""
    if records:
        record = list(records.values())[-1]
        source = "agent" if _model_written(record) else "template"
        return {"minute": record.minute, "kind": record.kind, **record.explanation, "source": source}
    if recent:
        context = recent[-1]
        explanation = explanation_template(context).model_dump(mode="json")
        return {"minute": context.moment.minute_label, "kind": context.moment.kind.value, **explanation,
                "source": "template"}
    return None


def studio_payload(metadata: MatchMetadata, events: Sequence[MatchEvent], frames: Sequence[FrameRecord],
                   records: Mapping[str, BroadcastRecord], recent: Sequence[MomentContext],
                   window: StudioWindow, shape: Mapping[str, object]) -> dict[str, object]:
    """Heat, pressing, and pass maps per team, space control (with the players) from the latest frame, the
    recommended visual, and shape (the whole match's line-height timeline and shifts, whatever the window)."""
    played = _window(events, window)
    home_id = metadata.home.team_id
    teams = {}
    for side, team in (("home", metadata.home), ("away", metadata.away)):
        teams[side] = {"team_id": team.team_id, "heat": density(played, team.team_id, home_id, ON_BALL),
                       "pressing": density(played, team.team_id, home_id, DEFENSIVE),
                       "network": pass_network(played, team.team_id, home_id).to_dict()}
    home_ids = frozenset(p.player_id for p in metadata.home.players)
    control = None
    if frames:
        control = space_control(frames[-1].positions, home_ids).to_dict() | {
            "positions": [list(p) for p in frames[-1].positions]}
    pick = _analyst_pick(records, recent)
    theme = str(pick.get("theme")) if pick else None
    return {"window": window.value, "events": len(played), "teams": teams, "control": control,
            "analyst": pick, "recommended": visual_for(theme).value, "shape": dict(shape)}
