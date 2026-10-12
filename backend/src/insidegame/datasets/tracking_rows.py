"""Pure conversion of a simulated match into sampled 22-player tracking rows for the dataset.

The tracking model is stepped through every event so its possession and ball state stay correct, but only every
Nth frame is kept to bound file size. Each row carries the match clock, ball location, and all 22 positions in
the absolute home frame, matching the event table's coordinate convention.
"""

from insidegame.datasets.rows import COORD_DECIMALS, Row
from insidegame.domain.match import MatchResult
from insidegame.tracking.model import TrackingModel

DEFAULT_SAMPLE_EVERY: int = 5


def tracking_rows(result: MatchResult, sample_every: int = DEFAULT_SAMPLE_EVERY) -> list[Row]:
    """Return one row per sampled event: clock, ball position, and [player_id, x, y] for all 22 players.

    The default keeps every fifth frame (DEFAULT_SAMPLE_EVERY); pass 1 to keep every frame.
    """
    model = TrackingModel(result.metadata)
    rows: list[Row] = []
    for index, event in enumerate(result.events):
        frame = model.frame(event)
        if index % sample_every:
            continue
        ball = model.ball_home_frame
        rows.append({
            "match_id": result.metadata.match_id, "event_id": event.event_id, "sequence": event.sequence,
            "period": event.period, "match_second": round(event.match_second, COORD_DECIMALS),
            "ball_x": round(ball.x, COORD_DECIMALS), "ball_y": round(ball.y, COORD_DECIMALS),
            "players": [[pid, x, y] for pid, x, y in frame],
        })
    return rows
