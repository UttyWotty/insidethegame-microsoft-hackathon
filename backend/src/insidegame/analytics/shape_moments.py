"""Pure facts, trigger, and summary sentence of a shape_shift key moment.

The trigger names the goal that changed the game state before the shift (going ahead, conceding, and so on), and
the facts carry the before and after back-line height, block, length, width, space control, and possession.
Every number in the summary is also a fact, so agents can cite it and the grounding check accepts it.
"""

from enum import StrEnum

from insidegame.analytics.moments import FactValue
from insidegame.analytics.rhythm import PRESSURE_STATE_THRESHOLD, RhythmReading
from insidegame.analytics.shape import SHAPE_DECIMALS, block_for
from insidegame.analytics.shape_tracker import PERCENT_DECIMALS, ShapeShift, ShiftDirection
from insidegame.core.clock import minute_label
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.domain.match import MatchMetadata

SHAPE_SHIFT_IMPORTANCE: float = 0.56
NO_MOMENTUM: str = "neither"
SHAPE_SUMMARY: str = "{lead}{team}'s back line {verb} from {line_before_m} m to {line_after_m} m"
CONTROL_CLAUSE: str = "their share of the pitch went from {control_before_pct}% to {control_after_pct}%"
POSSESSION_CLAUSE: str = "their possession from {possession_before_pct}% to {possession_after_pct}%"
POSSESSION_ALONE_CLAUSE: str = "their possession went from {possession_before_pct}% to {possession_after_pct}%"
SAME_MINUTES: str = "; over the same {minutes_compared} minutes "
CLAUSE_JOINER: str = " and "
TRIGGER_LEAD: str = "After {phrase} at {trigger_minute}, "
DIRECTION_VERBS: dict[ShiftDirection, str] = {ShiftDirection.DROPPED: "dropped",
                                              ShiftDirection.PUSHED_UP: "pushed up"}


class ShiftTrigger(StrEnum):
    """The game-state change that preceded a shift, from the shifting team's point of view."""

    WENT_AHEAD = "went_ahead"
    EXTENDED_LEAD = "extended_lead"
    EQUALISED = "equalised"
    PULLED_ONE_BACK = "pulled_one_back"
    CONCEDED = "conceded"
    NONE = "none"


TRIGGER_PHRASES: dict[ShiftTrigger, str] = {
    ShiftTrigger.WENT_AHEAD: "going ahead", ShiftTrigger.EXTENDED_LEAD: "extending the lead",
    ShiftTrigger.EQUALISED: "equalising", ShiftTrigger.PULLED_ONE_BACK: "pulling one back",
    ShiftTrigger.CONCEDED: "conceding",
}


def _goal_difference(team_id: str, metadata: MatchMetadata, score_home: int, score_away: int) -> int:
    diff = score_home - score_away
    return diff if team_id == metadata.home.team_id else -diff


def shift_trigger(shift: ShapeShift, metadata: MatchMetadata) -> ShiftTrigger:
    """Classify the latest goal before the shift; NONE when no goal of the period falls in the compared windows."""
    if shift.last_goal is None:
        return ShiftTrigger.NONE
    scorer, _, score_home, score_away = shift.last_goal
    if scorer != shift.team_id:
        return ShiftTrigger.CONCEDED
    diff = _goal_difference(shift.team_id, metadata, score_home, score_away)
    if diff == 0:
        return ShiftTrigger.EQUALISED
    if diff < 0:
        return ShiftTrigger.PULLED_ONE_BACK
    return ShiftTrigger.WENT_AHEAD if diff == 1 else ShiftTrigger.EXTENDED_LEAD


def _pct(value: float | None) -> float | None:
    return None if value is None else round(value, PERCENT_DECIMALS)


def _summary(facts: dict[str, FactValue], trigger: ShiftTrigger, direction: ShiftDirection) -> str:
    """The summary sentence from the rounded facts; clauses without values are left out."""
    lead = "" if trigger is ShiftTrigger.NONE else TRIGGER_LEAD.format(
        phrase=TRIGGER_PHRASES[trigger], trigger_minute=facts["trigger_minute"])
    text = SHAPE_SUMMARY.format(lead=lead, verb=DIRECTION_VERBS[direction], **facts)
    clauses = []
    if facts["control_before_pct"] is not None and facts["control_after_pct"] is not None:
        clauses.append(CONTROL_CLAUSE.format(**facts))
    if facts["possession_before_pct"] is not None and facts["possession_after_pct"] is not None:
        clauses.append((POSSESSION_CLAUSE if clauses else POSSESSION_ALONE_CLAUSE).format(**facts))
    return text + (SAME_MINUTES.format(**facts) + CLAUSE_JOINER.join(clauses) if clauses else "")


def _momentum_with(reading: RhythmReading, metadata: MatchMetadata) -> str:
    if reading.momentum >= PRESSURE_STATE_THRESHOLD:
        return metadata.home.name
    return metadata.away.name if reading.momentum <= -PRESSURE_STATE_THRESHOLD else NO_MOMENTUM


def shape_facts(shift: ShapeShift, metadata: MatchMetadata, reading: RhythmReading) -> dict[str, FactValue]:
    """The documented fact set of a shape_shift moment, with metres and percentages to one decimal."""
    names = {metadata.home.team_id: metadata.home.name, metadata.away.team_id: metadata.away.name}
    trigger = shift_trigger(shift, metadata)
    before, after = shift.before, shift.after
    facts: dict[str, FactValue] = {
        "team": names[shift.team_id], "opponent": names[shift.opponent_id], "direction": shift.direction.value,
        "line_before_m": round(before.line_height_m, SHAPE_DECIMALS),
        "line_after_m": round(after.line_height_m, SHAPE_DECIMALS),
        "line_change_m": round(shift.line_change_m, SHAPE_DECIMALS),
        "block_before": block_for(before.line_height_m).value, "block_after": block_for(after.line_height_m).value,
        "length_before_m": round(before.length_m, SHAPE_DECIMALS), "length_after_m": round(after.length_m, SHAPE_DECIMALS),
        "width_before_m": round(before.width_m, SHAPE_DECIMALS), "width_after_m": round(after.width_m, SHAPE_DECIMALS),
        "control_before_pct": _pct(before.control_pct), "control_after_pct": _pct(after.control_pct),
        "possession_before_pct": _pct(before.possession_pct), "possession_after_pct": _pct(after.possession_pct),
        "minutes_compared": int(shift.window_s // SECONDS_PER_MINUTE),
        "score": f"{shift.score_home}-{shift.score_away}",
        "goal_difference": _goal_difference(shift.team_id, metadata, shift.score_home, shift.score_away),
        "trigger": trigger.value,
        "trigger_minute": minute_label(shift.last_goal[1], shift.period) if shift.last_goal else None,
        "momentum_with": _momentum_with(reading, metadata),
    }
    facts["summary"] = _summary(facts, trigger, shift.direction)
    return facts
