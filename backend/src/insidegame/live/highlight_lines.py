"""Chooses the narration for each highlights clip from what a live session has already produced.

A viewer segment's own cue commentary wins, because it is in that viewer's language and persona; otherwise the
producer desk's record supplies the moment's produced commentary in English. Moments with neither are left out,
so the reel builder falls back to a grounded caption from the facts.
"""

from collections.abc import Iterable, Mapping

from insidegame.highlights.reel import DEFAULT_LANGUAGE, Narration
from insidegame.live.producer import BroadcastRecord


def clip_narrations(segment_cues: Iterable[Mapping[str, object]],
                    records: Mapping[str, BroadcastRecord]) -> dict[str, Narration]:
    """Map moment ids to narration, preferring the segment's own cue commentary over the desk record."""
    narrations = {moment_id: Narration(record.commentary) for moment_id, record in records.items()
                  if record.commentary}
    for cue in segment_cues:
        text = str(cue.get("commentary") or "")
        if text:
            language = str(cue.get("commentary_language") or DEFAULT_LANGUAGE)
            narrations[str(cue["moment_id"])] = Narration(text, language)
    return narrations
