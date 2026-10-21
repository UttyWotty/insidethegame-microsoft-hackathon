"""Pure conversion of an analysed match into flat dataset rows.

Events are enriched with absolute pitch coordinates (home attacking left to right throughout), xG, pass difficulty,
expected threat (xT) added by completed passes and carries, and the key moment they triggered, so each row is
self-contained for analytics and supervised learning.
"""

from dataclasses import dataclass, field

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.threat import XT_DECIMALS
from insidegame.core.clock import minute_label
from insidegame.core.geometry import Point, mirror
from insidegame.domain.match import MatchResult

Row = dict[str, object]
COORD_DECIMALS: int = 2


@dataclass(frozen=True)
class MatchTables:
    """All dataset rows produced from one match."""

    match: Row
    events: list[Row] = field(default_factory=list)
    players: list[Row] = field(default_factory=list)
    moments: list[Row] = field(default_factory=list)


def _absolute(point: Point | None, is_home: bool) -> tuple[float | None, float | None]:
    if point is None:
        return None, None
    absolute = point if is_home else mirror(point)
    return round(absolute.x, COORD_DECIMALS), round(absolute.y, COORD_DECIMALS)


def _event_rows(result: MatchResult, analyzer: MatchAnalyzer) -> list[Row]:
    rows: list[Row] = []
    home_id = result.metadata.home.team_id
    for event in result.events:
        update = analyzer.ingest(event)
        is_home = event.team_id == home_id
        start_x, start_y = _absolute(event.start, is_home)
        end_x, end_y = _absolute(event.end, is_home)
        base = event.to_dict()
        base.pop("start"), base.pop("end"), base.pop("score")
        rows.append(base | {
            "seed": result.metadata.seed, "side": None if event.team_id is None else ("home" if is_home else "away"),
            "minute_label": minute_label(event.match_second, event.period),
            "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y,
            "score_home": event.score_home, "score_away": event.score_away,
            "xg": update.xg, "pass_difficulty": update.pass_quality.difficulty if update.pass_quality else None,
            "momentum": round(update.rhythm.momentum, COORD_DECIMALS), "rhythm_state": update.rhythm.state.value,
            "xt_added": round(update.threat.xt_added, XT_DECIMALS) if update.threat else None,
            "moment_kinds": [m.kind.value for m in update.moments],
        })
    return rows


def build_tables(result: MatchResult) -> MatchTables:
    """Analyse a match from scratch and return its dataset tables."""
    metadata = result.metadata
    analyzer = MatchAnalyzer(metadata)
    events = _event_rows(result, analyzer)
    stats = analyzer.stats
    match: Row = {
        "match_id": metadata.match_id, "seed": metadata.seed, "competition": metadata.competition,
        "venue": metadata.venue, "home": metadata.home.name, "away": metadata.away.name,
        "home_team_id": metadata.home.team_id, "away_team_id": metadata.away.team_id,
        "home_style": metadata.home.style.label, "away_style": metadata.away.style.label,
        "home_goals": result.home_goals, "away_goals": result.away_goals, "events": len(result.events),
        "home_possession_pct": round(stats.possession_share(metadata.home.team_id), COORD_DECIMALS),
        "home_xg": round(stats.teams[metadata.home.team_id].xg, COORD_DECIMALS),
        "away_xg": round(stats.teams[metadata.away.team_id].xg, COORD_DECIMALS),
        "key_moments": len(analyzer.moments),
    }
    positions = {p.player_id: p for team in (metadata.home, metadata.away) for p in team.players}
    players = [{"match_id": metadata.match_id, **s.to_dict(), "position": positions[s.player_id].position.value,
                "shirt_number": positions[s.player_id].shirt_number} for s in stats.players.values()]
    moments = [{"match_id": metadata.match_id, **m.to_dict()} for m in analyzer.moments]
    return MatchTables(match, events, players, moments)
