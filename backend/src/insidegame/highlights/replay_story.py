"""Pure instant-replay story for one shot: build-up keyframes, the strike, the ball's flight, and the shot analysis.

Keyframes are built from events (true start and end points and times) plus the tracking frame stored after each
event for player positions, so the ball travels along each pass and carry and then into the goal mouth where the
shot card says it crossed the line, stops at the blocker for a blocked shot, or stops in front of the line at the
keeper for a saved shot, with the keeper shown at the save. Coordinates are in the absolute home
frame, and only stored analytics are used.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from insidegame.analytics.shot_block import block_point
from insidegame.analytics.shot_card import ShotCard
from insidegame.analytics.shot_save import save_point
from insidegame.analytics.threat import ThreatAction
from insidegame.core.constants import GOAL_CENTER_Y_M, PITCH_LENGTH_M
from insidegame.core.geometry import GOAL_CENTER, Point, distance
from insidegame.domain.enums import EventType, Position, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights.replay_analysis import (
    ShotAnalysis,
    analyse_shot,
    completed_actions,
    rounded,
    shot_opponents,
    team_possession,
    to_absolute,
)
from insidegame.tracking.model import Frame

REPLAY_MAX_ACTIONS: int = 4
REPLAY_MAX_LEAD_S: float = 12.0
SHOT_MATCH_TOLERANCE_S: float = 0.01
FLOAT_EPSILON: float = 1e-9
MIN_FLIGHT_S: float = 0.4
DEFAULT_SHOT_SPEED_KMH: float = 90.0
KMH_PER_MS: float = 3.6
BALL_DECIMALS: int = 1


class ReplayPhase(StrEnum):
    """Which part of the replay a keyframe belongs to."""

    BUILD_UP = "build_up"
    SHOT = "shot"
    FLIGHT = "flight"


@dataclass(frozen=True)
class ReplayKeyframe:
    """One replay keyframe in the absolute home frame; its dict is a superset of FrameRecord.to_dict()."""

    period: int
    match_second: float
    phase: ReplayPhase
    event_type: str
    player_id: str | None
    receiver_id: str | None
    ball: tuple[float, float]
    positions: Frame

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"period": self.period, "match_second": self.match_second, "phase": self.phase.value,
                "event_type": self.event_type, "player_id": self.player_id, "receiver_id": self.receiver_id,
                "ball": list(self.ball), "positions": [list(p) for p in self.positions]}


@dataclass(frozen=True)
class ReplayStory:
    """The keyframes and analysis of one shot's instant replay."""

    period: int
    at: float
    keyframes: list[ReplayKeyframe]
    analysis: ShotAnalysis

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"period": self.period, "at": self.at, "frames": [k.to_dict() for k in self.keyframes],
                "analysis": self.analysis.to_dict()}


def find_shot(events: Sequence[MatchEvent], period: int, at: float) -> int | None:
    """Index of the shot in period within SHOT_MATCH_TOLERANCE_S of at, or None when no shot matches.

    FLOAT_EPSILON absorbs binary rounding, so a second exactly at the tolerance still matches.
    """
    return next((i for i, e in enumerate(events) if e.event_type is EventType.SHOT and e.period == period
                 and abs(e.match_second - at) <= SHOT_MATCH_TOLERANCE_S + FLOAT_EPSILON), None)


def build_up_actions(events: Sequence[MatchEvent], shot_index: int) -> list[MatchEvent]:
    """The shooting team's last REPLAY_MAX_ACTIONS completed passes and carries of the possession, oldest first.

    Only actions no more than REPLAY_MAX_LEAD_S before the shot, with a start and end, are kept.
    """
    earliest = events[shot_index].match_second - REPLAY_MAX_LEAD_S
    actions = [e for e in completed_actions(team_possession(events, shot_index))
               if e.match_second >= earliest and e.start is not None and e.end is not None]
    return actions[-REPLAY_MAX_ACTIONS:]


def flight_end(shot: MatchEvent, card: ShotCard, outfield: Sequence[Point], keeper: Point | None) -> Point:
    """Where the ball finishes in the shooter's attacking frame.

    A saved shot with a card placement stops in front of the line where the keeper meets it (save_point); any other
    shot with a placement goes to the card's goal-line placement, else to the shot's end. A blocked shot without an
    end (as the simulator emits them) stops at the blocker among the outfield opponents, or a short way out
    (block_point); any other shot without an end goes to GOAL_CENTER. The shot must have a start.
    """
    assert shot.start is not None
    if card.placement_y is not None and shot.shot_result is ShotResult.SAVED:
        return save_point(shot.start, card.placement_y, keeper)
    if card.placement_y is not None:
        return Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M + card.placement_y)
    if shot.end is not None:
        return shot.end
    return block_point(shot.start, outfield) if shot.shot_result is ShotResult.BLOCKED else GOAL_CENTER


def flight_seconds(origin: Point, end: Point, speed_kmh: float | None) -> float:
    """Seconds the ball takes from origin to end at speed_kmh (DEFAULT_SHOT_SPEED_KMH when None), at least MIN_FLIGHT_S."""
    speed_ms = (speed_kmh or DEFAULT_SHOT_SPEED_KMH) / KMH_PER_MS
    return max(distance(origin, end) / speed_ms, MIN_FLIGHT_S)


def aligned_frame(frame: Frame, player_id: str | None, spot: tuple[float, float]) -> Frame:
    """The frame with the acting player moved onto spot (display alignment only; no number is derived from it)."""
    return [(pid, *spot) if pid == player_id else (pid, x, y) for pid, x, y in frame]


def action_keyframe(action: MatchEvent, frame: Frame, team_id: str, metadata: MatchMetadata) -> ReplayKeyframe:
    """The BUILD_UP keyframe of a pass or carry: the ball at its start in team_id's absolute frame, at its second.

    frame is the tracking frame stored after the action; its player is aligned on the ball. The action must have a
    start.
    """
    assert action.start is not None
    ball = rounded(to_absolute(action.start, team_id, metadata), BALL_DECIMALS)
    return ReplayKeyframe(action.period, action.match_second, ReplayPhase.BUILD_UP, action.event_type.value,
                          action.player_id, action.receiver_id, ball, aligned_frame(frame, action.player_id, ball))


def _keeper_id(shot: MatchEvent, metadata: MatchMetadata) -> str | None:
    """The defending goalkeeper's player id, or None when the opponents list no goalkeeper. The shot must have a team."""
    assert shot.team_id is not None
    opponents = metadata.team(metadata.side_of(shot.team_id).opponent).players
    return next((p.player_id for p in opponents if p.position is Position.GOALKEEPER), None)


def _flight_positions(shot: MatchEvent, shot_positions: Frame, landing: tuple[float, float],
                      metadata: MatchMetadata) -> Frame:
    """The FLIGHT keyframe's positions: the shot frame, with the defending keeper on the ball for a saved shot."""
    if shot.shot_result is not ShotResult.SAVED:
        return shot_positions
    return aligned_frame(shot_positions, _keeper_id(shot, metadata), landing)


def build_keyframes(shot: MatchEvent, actions: Sequence[MatchEvent], frames: Mapping[str, Frame], card: ShotCard,
                    metadata: MatchMetadata) -> list[ReplayKeyframe]:
    """BUILD_UP keyframes for actions with a stored frame, then SHOT and FLIGHT keyframes from the shot's frame.

    Each BUILD_UP ball is the action's start; the SHOT ball is the shot's start; the FLIGHT ball is flight_end at
    the shot time plus flight_seconds. The shooter stays at the shot origin during the flight; for a saved shot the
    defending keeper moves onto the save point in the FLIGHT keyframe. The shot must have a team, start, and stored
    frame.
    """
    assert shot.team_id is not None and shot.start is not None
    team_id = shot.team_id
    keyframes = []
    for action in actions:
        if action.event_id not in frames or action.start is None:
            continue
        keyframes.append(action_keyframe(action, frames[action.event_id], team_id, metadata))
    origin = rounded(to_absolute(shot.start, team_id, metadata), BALL_DECIMALS)
    shot_positions = aligned_frame(frames[shot.event_id], shot.player_id, origin)
    outfield, keeper = shot_opponents(shot, frames[shot.event_id], metadata)
    end = flight_end(shot, card, outfield, keeper)
    landing = rounded(to_absolute(end, team_id, metadata), BALL_DECIMALS)
    arrival = shot.match_second + flight_seconds(shot.start, end, shot.ball_speed_kmh)
    keyframes.append(ReplayKeyframe(shot.period, shot.match_second, ReplayPhase.SHOT, shot.event_type.value,
                                    shot.player_id, None, origin, shot_positions))
    keyframes.append(ReplayKeyframe(shot.period, arrival, ReplayPhase.FLIGHT, shot.event_type.value,
                                    shot.player_id, None, landing,
                                    _flight_positions(shot, shot_positions, landing, metadata)))
    return keyframes


def build_story(events: Sequence[MatchEvent], frames: Mapping[str, Frame], threats: Mapping[str, ThreatAction],
                metadata: MatchMetadata, period: int, at: float) -> ReplayStory | None:
    """The replay story of the played shot at (period, at), or None when no shot matches or its frame is missing.

    frames and threats map event ids to the stored tracking frame and live threat assessment of each event.
    """
    index = find_shot(events, period, at)
    if index is None:
        return None
    shot = events[index]
    if shot.event_id not in frames or shot.team_id is None or shot.player_id is None or shot.start is None:
        return None
    actions = [a for a in build_up_actions(events, index) if a.event_id in frames]
    analysis = analyse_shot(events, index, actions, frames[shot.event_id], threats, metadata)
    keyframes = build_keyframes(shot, actions, frames, analysis.card, metadata)
    return ReplayStory(period, at, keyframes, analysis)
