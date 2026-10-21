"""Pure mapping from a highlights-reel moment to the instant-replay keyframes of the shot it is about.

A moment is about a shot when its event ids hold a SHOT, or a GOAL whose same-second SHOT find_shot locates.
Such a clip reuses build_story unchanged, so the reel shows the real build-up and the ball's flight exactly as
the instant replay does; any other moment has no story and keeps its stored frames.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from insidegame.analytics.moments import KeyMoment
from insidegame.analytics.threat import ThreatAction
from insidegame.domain.enums import EventType
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights.replay_story import ReplayKeyframe, build_story, find_shot
from insidegame.tracking.model import Frame


@dataclass(frozen=True)
class StorySource:
    """Everything build_story needs apart from the shot's period and second: played events, frames, and threats.

    frames and threats map event ids to the stored tracking frame and live threat assessment of each event.
    """

    events: Sequence[MatchEvent]
    frames: Mapping[str, Frame]
    threats: Mapping[str, ThreatAction]
    metadata: MatchMetadata


def moment_shot(moment: KeyMoment, events: Sequence[MatchEvent]) -> MatchEvent | None:
    """The shot a moment is about, or None when the moment is not about a shot.

    The first SHOT among the moment's event ids wins; otherwise a GOAL id maps to the SHOT find_shot matches at the
    goal's period and second. Event ids missing from events are ignored.
    """
    by_id = {e.event_id: e for e in events}
    named = [by_id[eid] for eid in moment.event_ids if eid in by_id]
    shot = next((e for e in named if e.event_type is EventType.SHOT), None)
    if shot is not None:
        return shot
    goal = next((e for e in named if e.event_type is EventType.GOAL), None)
    if goal is None:
        return None
    index = find_shot(events, goal.period, goal.match_second)
    return events[index] if index is not None else None


def clip_story(moment: KeyMoment, source: StorySource) -> list[ReplayKeyframe] | None:
    """The replay keyframes of the moment's shot, or None when it has no shot or build_story cannot tell its story."""
    shot = moment_shot(moment, source.events)
    if shot is None:
        return None
    story = build_story(source.events, source.frames, source.threats, source.metadata, shot.period, shot.match_second)
    return story.keyframes if story is not None else None
