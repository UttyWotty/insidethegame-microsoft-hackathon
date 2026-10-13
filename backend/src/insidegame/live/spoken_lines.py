"""Pure lookup of a commentary line a live session produced, so only real match commentary is ever voiced.

Play-by-play lines are found by their line id and are in English; agent commentary on a moment is found in the
cue history of the viewer segment it was delivered to, in the language recorded on that cue. A reference that
the session does not hold raises LineNotFoundError, which keeps the speech endpoint from voicing arbitrary text.
"""

from collections.abc import Iterable, Mapping

from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.core.exceptions import LineNotFoundError

MOMENT_REF_PREFIX: str = "moment-"


def find_spoken_line(ref: str, segment: str | None, commentary: Iterable[Mapping[str, object]],
                     cue_history: Mapping[str, Iterable[Mapping[str, object]]]) -> tuple[str, str]:
    """Return (text, language) for a play-by-play line id, or for moment-<moment_id> within a segment's cues."""
    if ref.startswith(MOMENT_REF_PREFIX):
        moment_id = ref.removeprefix(MOMENT_REF_PREFIX)
        for cue in cue_history.get(segment or "", ()):
            if cue["moment_id"] == moment_id:
                return str(cue["commentary"]), str(cue["commentary_language"])
    else:
        for line in commentary:
            if line["line_id"] == ref:
                return str(line["text"]), DEFAULT_LANGUAGE
    raise LineNotFoundError(f"No commentary line {ref!r} in this match")
