"""Pure analysis block of an instant replay: the shot card, goal chance, shot cone, assist, and build-up of one shot.

Every number comes from existing analytics (xG, the shot card, pass quality, and the stored expected threat of each
pass and carry), so the replay never shows a figure the live broadcast did not compute.
The cone and the build-up path are output in the absolute home frame, ready to draw on the pitch.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from insidegame.analytics.pass_quality import assess_pass
from insidegame.analytics.shot_card import ShotCard, shot_card
from insidegame.analytics.shot_cone import cone_occupancy, cone_points
from insidegame.analytics.threat import XT_DECIMALS, ThreatAction
from insidegame.analytics.xg import expected_goals
from insidegame.core.geometry import Point, distance, mirror
from insidegame.domain.enums import EventType, Outcome, Position, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.tracking.model import Frame

PERCENT: int = 100
DURATION_DECIMALS: int = 1
LENGTH_DECIMALS: int = 1
POINT_DECIMALS: int = 2
BUILD_UP_TYPES: frozenset[EventType] = frozenset({EventType.PASS, EventType.CARRY})


@dataclass(frozen=True)
class AssistInfo:
    """The last completed pass to the shooter in the possession; threat fields are None or empty without a threat."""

    passer_id: str
    length_m: float
    difficulty: float | None
    xt_added: float | None
    opponents_bypassed: int | None
    lines_broken: list[str]
    breaks_line: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"passer_id": self.passer_id, "length_m": self.length_m, "difficulty": self.difficulty,
                "xt_added": self.xt_added, "opponents_bypassed": self.opponents_bypassed,
                "lines_broken": list(self.lines_broken), "breaks_line": self.breaks_line}


@dataclass(frozen=True)
class BuildUpInfo:
    """Completed passes, time on the ball, and xT built by the shooting team's possession, with the drawn path."""

    passes: int
    duration_s: float
    xt_added: float
    path: list[tuple[float, float]]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"passes": self.passes, "duration_s": self.duration_s, "xt_added": self.xt_added,
                "path": [list(p) for p in self.path]}


@dataclass(frozen=True)
class ShotAnalysis:
    """Everything the replay's analysis card and pitch graphics show about one shot.

    xg is the model value at XG_DECIMALS precision, from which goal_chance_pct is derived; card.xg is the
    broadcast's two-decimal figure.
    """

    shot_event_id: str
    shooter_id: str
    team_id: str
    card: ShotCard
    xg: float
    goal_chance_pct: int
    under_pressure: bool
    cone: tuple[tuple[float, float], ...]
    defenders_in_cone: int
    keeper_in_cone: bool
    build_up: BuildUpInfo
    assist: AssistInfo | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation with the card, build-up, and assist nested."""
        return {"shot_event_id": self.shot_event_id, "shooter_id": self.shooter_id, "team_id": self.team_id,
                "card": self.card.to_dict(), "xg": self.xg, "goal_chance_pct": self.goal_chance_pct,
                "under_pressure": self.under_pressure, "cone": [list(p) for p in self.cone],
                "defenders_in_cone": self.defenders_in_cone, "keeper_in_cone": self.keeper_in_cone,
                "build_up": self.build_up.to_dict(), "assist": self.assist.to_dict() if self.assist else None}


def to_absolute(point: Point, team_id: str, metadata: MatchMetadata) -> Point:
    """Convert a point in a team's attacking frame to the absolute home frame (mirrored for the away team)."""
    return point if metadata.side_of(team_id) is Side.HOME else mirror(point)


def rounded(point: Point, decimals: int) -> tuple[float, float]:
    """A point as an (x, y) pair rounded to decimals."""
    return round(point.x, decimals), round(point.y, decimals)


def team_possession(events: Sequence[MatchEvent], shot_index: int) -> list[MatchEvent]:
    """Events of the shooter's team in the shot's possession before the shot, oldest first."""
    shot = events[shot_index]
    return [e for e in events[:shot_index]
            if e.possession_id == shot.possession_id and e.team_id == shot.team_id and e.period == shot.period]


def completed_actions(possession: Sequence[MatchEvent]) -> list[MatchEvent]:
    """Completed passes and carries among the possession's events, oldest first."""
    return [e for e in possession if e.event_type in BUILD_UP_TYPES and e.outcome is Outcome.SUCCESS]


def _assist(actions: Sequence[MatchEvent], shooter_id: str, threats: Mapping[str, ThreatAction]) -> AssistInfo | None:
    """The last completed pass received by the shooter, with its difficulty and stored threat."""
    passes = [e for e in actions if e.event_type is EventType.PASS and e.receiver_id == shooter_id
              and e.player_id is not None and e.start is not None and e.end is not None]
    if not passes:
        return None
    last = passes[-1]
    assert last.player_id is not None and last.start is not None and last.end is not None
    length = last.length_m if last.length_m is not None else distance(last.start, last.end)
    threat = threats.get(last.event_id)
    line_break = threat.line_break if threat else None
    return AssistInfo(
        passer_id=last.player_id, length_m=round(length, LENGTH_DECIMALS),
        difficulty=assess_pass(last.start, last.end, last.under_pressure).difficulty,
        xt_added=round(threat.xt_added, XT_DECIMALS) if threat else None,
        opponents_bypassed=line_break.opponents_bypassed if line_break else None,
        lines_broken=[line.value for line in line_break.lines_broken] if line_break else [],
        breaks_line=threat.breaks_line if threat else False)


def _build_up(events: Sequence[MatchEvent], shot_index: int, shown: Sequence[MatchEvent],
              threats: Mapping[str, ThreatAction], metadata: MatchMetadata) -> BuildUpInfo:
    """Pass count, possession duration, summed xT, and the drawn path of the shot's build-up."""
    shot = events[shot_index]
    assert shot.team_id is not None and shot.start is not None
    possession = team_possession(events, shot_index)
    actions = completed_actions(possession)
    passes = sum(1 for e in actions if e.event_type is EventType.PASS)
    first = possession[0].match_second if possession else shot.match_second
    xt = sum(threats[e.event_id].xt_added for e in actions if e.event_id in threats)
    team_id = shot.team_id
    path = [rounded(to_absolute(e.start, team_id, metadata), POINT_DECIMALS) for e in shown if e.start is not None]
    path.append(rounded(to_absolute(shot.start, team_id, metadata), POINT_DECIMALS))
    return BuildUpInfo(passes, round(shot.match_second - first, DURATION_DECIMALS), round(xt, XT_DECIMALS), path)


def shot_opponents(shot: MatchEvent, shot_frame: Frame, metadata: MatchMetadata) -> tuple[list[Point], Point | None]:
    """The shooter's opponents in the stored shot frame, in the shooter's attacking frame: outfield, then the keeper.

    Teammates are never included; the keeper is None when absent from the frame. The shot must have a team.
    """
    assert shot.team_id is not None
    side = metadata.side_of(shot.team_id)
    opponents = metadata.team(side.opponent).players
    keeper_ids = {p.player_id for p in opponents if p.position is Position.GOALKEEPER}
    outfield_ids = {p.player_id for p in opponents} - keeper_ids
    located = {pid: to_absolute(Point(x, y), shot.team_id, metadata) for pid, x, y in shot_frame}
    keeper = next((located[pid] for pid in keeper_ids if pid in located), None)
    return [located[pid] for pid in sorted(outfield_ids) if pid in located], keeper


def _cone(shot: MatchEvent, shot_frame: Frame, metadata: MatchMetadata) -> tuple[tuple[tuple[float, float], ...], int, bool]:
    """The absolute-frame cone, and opponents in it from the stored shot frame (teammates never counted)."""
    assert shot.team_id is not None and shot.start is not None
    outfield, keeper = shot_opponents(shot, shot_frame, metadata)
    occupancy = cone_occupancy(shot.start, outfield, keeper)
    cone = tuple(rounded(to_absolute(p, shot.team_id, metadata), POINT_DECIMALS) for p in cone_points(shot.start))
    return cone, occupancy.defenders, occupancy.keeper


def analyse_shot(events: Sequence[MatchEvent], shot_index: int, shown: Sequence[MatchEvent], shot_frame: Frame,
                 threats: Mapping[str, ThreatAction], metadata: MatchMetadata) -> ShotAnalysis:
    """Analyse the shot at shot_index; shown lists the build-up actions the replay plays, oldest first.

    shot_frame holds absolute home-frame positions stored after the shot; the shot must have a team, player, and
    start location.
    """
    shot = events[shot_index]
    assert shot.team_id is not None and shot.player_id is not None and shot.start is not None
    xg = expected_goals(shot.start, shot.under_pressure)
    card = shot_card(shot, xg)
    cone, defenders, keeper = _cone(shot, shot_frame, metadata)
    actions = completed_actions(team_possession(events, shot_index))
    return ShotAnalysis(shot.event_id, shot.player_id, shot.team_id, card, xg, round(xg * PERCENT),
                        shot.under_pressure, cone, defenders, keeper,
                        _build_up(events, shot_index, shown, threats, metadata),
                        _assist(actions, shot.player_id, threats))
