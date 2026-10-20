"""Pure keyframes for non-shot highlights clips: the passes and carries played in the clip's window, in order.

Each action becomes a BUILD_UP keyframe built exactly like the instant replay's build-up (the ball at the action's
true start with the acting player aligned on it, each completed pass followed by its reception), and a final keyframe
lands the ball at the last action's end when the next event happens; off-ball motion is smoothed the same way too.
Shot moments and windows without a pass or carry get no sequence, so their clips keep the
shot's story or the stored frames.
"""

from collections.abc import Mapping, Sequence

from insidegame.analytics.moments import KeyMoment
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights.reel_story import StorySource, moment_shot
from insidegame.highlights.replay_analysis import BUILD_UP_TYPES, rounded, to_absolute
from insidegame.highlights.replay_story import (
    BALL_DECIMALS,
    ReplayKeyframe,
    ReplayPhase,
    action_keyframe,
    aligned_frame,
    reception_keyframe,
    smooth_keyframes,
)
from insidegame.tracking.model import Frame

ARRIVAL_MAX_S: float = 5.0
ARRIVAL_MIN_S: float = 0.4


def window_actions(events: Sequence[MatchEvent], frames: Mapping[str, Frame], period: int, start_s: float,
                   end_s: float) -> list[int]:
    """Indices, in event order, of PASS and CARRY events (any outcome) in period with start_s <= second <= end_s.

    Only actions with a start, an end, a team, and a stored frame are kept.
    """
    return [i for i, e in enumerate(events)
            if e.event_type in BUILD_UP_TYPES and e.period == period and start_s <= e.match_second <= end_s
            and e.start is not None and e.end is not None and e.team_id is not None and e.event_id in frames]


def arrival_second(events: Sequence[MatchEvent], index: int) -> float:
    """When the ball of events[index] arrives: its second plus the gap to the next strictly later event.

    Only events in the same period count. The gap is clamped to [ARRIVAL_MIN_S, ARRIVAL_MAX_S] and is ARRIVAL_MAX_S
    when no later event exists.
    """
    action = events[index]
    later = next((e for e in events[index + 1:]
                  if e.period == action.period and e.match_second > action.match_second), None)
    gap = later.match_second - action.match_second if later is not None else ARRIVAL_MAX_S
    return action.match_second + min(max(gap, ARRIVAL_MIN_S), ARRIVAL_MAX_S)


def arrival_player(action: MatchEvent) -> str | None:
    """Who holds the ball at an action's end: the receiver of a completed pass, or the carrier of a carry.

    Any other action gives None, so no one is aligned. A failed pass keeps its intended receiver in receiver_id,
    but an opponent wins that ball, so the receiver is never used for it.
    """
    if action.event_type is EventType.PASS:
        return action.receiver_id if action.outcome is Outcome.SUCCESS else None
    if action.event_type is EventType.CARRY:
        return action.player_id
    return None


def arrival_keyframe(action: MatchEvent, frame: Frame, arrival: float, metadata: MatchMetadata) -> ReplayKeyframe:
    """The final BUILD_UP keyframe: the ball at the action's end at arrival, with the receiver or carrier on it.

    The aligned player comes from arrival_player. The action must have an end and a team.
    """
    assert action.end is not None and action.team_id is not None
    player_id = arrival_player(action)
    ball = rounded(to_absolute(action.end, action.team_id, metadata), BALL_DECIMALS)
    return ReplayKeyframe(action.period, arrival, ReplayPhase.BUILD_UP, action.event_type.value, player_id, None,
                          ball, aligned_frame(frame, player_id, ball))


def clip_sequence(moment: KeyMoment, source: StorySource, lead_s: float,
                  tail_s: float) -> list[ReplayKeyframe] | None:
    """Keyframes of the passes and carries from lead_s before the moment to tail_s after it, then the arrival.

    Each completed pass is followed by its reception keyframe, and off-ball motion is smoothed (smooth_keyframes).

    Returns None for a moment about a shot (it plays the shot's story or its stored frames) and for a window with
    no qualifying action.
    """
    if moment_shot(moment, source.events) is not None:
        return None
    events, frames = source.events, source.frames
    indices = window_actions(events, frames, moment.period, moment.match_second - lead_s,
                             moment.match_second + tail_s)
    if not indices:
        return None
    last = events[indices[-1]]
    arrival = arrival_second(events, indices[-1])
    keyframes = []
    for n, i in enumerate(indices):
        action = events[i]
        assert action.team_id is not None
        frame = frames[action.event_id]
        keyframes.append(action_keyframe(action, frame, action.team_id, source.metadata))
        next_second = events[indices[n + 1]].match_second if n + 1 < len(indices) else arrival
        reception = reception_keyframe(action, frame, action.team_id, source.metadata, next_second)
        if reception is not None:
            keyframes.append(reception)
    keyframes.append(arrival_keyframe(last, frames[last.event_id], arrival, source.metadata))
    return smooth_keyframes(keyframes)
