"""Pure display smoothing for replay keyframes: off-ball players never move faster than a running speed.

Tracked positions are formation shapes, so between two keyframes a player can jump tens of metres, which plays back
as a sprint across the pitch; capping each step keeps the motion believable while the players converge on their spots.
Players on the ball and every player at the last step are fixed anchors, so the ball sits at its player's feet and the
final frame (the strike in a replay) shows the true positions; only the moves in between are pulled within reach.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from insidegame.tracking.model import Frame

MAX_OFF_BALL_SPEED_MS: float = 7.0
ON_BALL_TOLERANCE_M: float = 0.05
SHOWN_DECIMALS: int = 1
SMOOTHING_PASSES: int = 4


@dataclass(frozen=True)
class MotionStep:
    """One keyframe as the smoothing sees it: its match second, the ball, and the tracked positions."""

    second: float
    ball: tuple[float, float]
    positions: Frame


@dataclass
class _Spot:
    """One player's shown spot at one step; anchored spots never move."""

    step: int
    second: float
    x: float
    y: float
    anchored: bool


def _pull(spot: _Spot, neighbour: _Spot, max_speed_ms: float) -> None:
    """Move an unanchored spot onto the edge of its neighbour's reach when it lies beyond it."""
    if spot.anchored:
        return
    reach = max_speed_ms * abs(spot.second - neighbour.second)
    gap = math.hypot(spot.x - neighbour.x, spot.y - neighbour.y)
    if gap <= reach:
        return
    share = reach / gap
    spot.x = neighbour.x + (spot.x - neighbour.x) * share
    spot.y = neighbour.y + (spot.y - neighbour.y) * share


def _tracks(steps: Sequence[MotionStep]) -> dict[str, list[_Spot]]:
    """Each player's spots in step order, anchored when on the ball or at the last step."""
    tracks: dict[str, list[_Spot]] = {}
    last = len(steps) - 1
    for index, step in enumerate(steps):
        for player_id, x, y in step.positions:
            anchored = index == last or math.dist((x, y), step.ball) <= ON_BALL_TOLERANCE_M
            tracks.setdefault(player_id, []).append(_Spot(index, step.second, x, y, anchored))
    return tracks


def capped_positions(steps: Sequence[MotionStep], max_speed_ms: float) -> list[Frame]:
    """The positions to show at each step (steps in time order), with off-ball moves capped at max_speed_ms.

    Spots start at the tracked positions; SMOOTHING_PASSES rounds of forward then backward passes pull every
    unanchored spot within max_speed_ms of its neighbours in time. Where two anchors are further apart than any run
    allows, the move between them stays fast. Shown positions are rounded to SHOWN_DECIMALS.
    """
    tracks = _tracks(steps)
    for track in tracks.values():
        for _ in range(SMOOTHING_PASSES):
            for k in range(1, len(track)):
                _pull(track[k], track[k - 1], max_speed_ms)
            for k in range(len(track) - 2, -1, -1):
                _pull(track[k], track[k + 1], max_speed_ms)
    shown = {(player_id, spot.step): spot for player_id, track in tracks.items() for spot in track}
    return [[(player_id, round(shown[player_id, index].x, SHOWN_DECIMALS),
              round(shown[player_id, index].y, SHOWN_DECIMALS)) for player_id, _, _ in step.positions]
            for index, step in enumerate(steps)]
