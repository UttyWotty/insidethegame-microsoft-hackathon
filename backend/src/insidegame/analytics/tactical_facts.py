"""Turns a recognised TacticalPattern into the named, JSON-scalar facts of a tactical_pattern key moment.

It resolves team names, the exposed full-back for a flank pattern, a readable flank label, and a summary sentence.
All wording comes from named templates, so every number in the summary is also present as a fact.
"""

from dataclasses import dataclass

from insidegame.analytics.moments import FactValue
from insidegame.analytics.pattern_rules import PatternKind, TacticalPattern
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.core.zones import Channel, opposite_flank
from insidegame.domain.enums import Position
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Player, Team

PERCENT: int = 100
RIGHT_BACK_INDEX: int = 0
LEFT_BACK_INDEX: int = 3
FLANK_EXPOSED_SUMMARY: str = "{team} beat {defender} down {flank_label}: {count} of {total} final-third entries in {window} minutes"
CHANNEL_OVERLOAD_SUMMARY: str = "{team} sent {count} of {total} final-third entries down the {channel} ({share}%) in {window} minutes"
TURNOVER_ZONE_SUMMARY: str = "{team} won the ball {count} times in the {third} third, {channel} channel, in {window} minutes"
FLANK_LABEL: str = "{opponent}'s {flank} flank"
CENTRE_LABEL: str = "the centre of {opponent}'s defence"
ZONE_LABEL: str = "the {third} third, {channel} channel"


@dataclass(frozen=True)
class TacticalEvidence:
    """Facts and involved players for one tactical_pattern moment."""

    facts: dict[str, FactValue]
    player_ids: tuple[str, ...]


def exposed_defender(pattern: TacticalPattern, metadata: MatchMetadata) -> Player | None:
    """The opponent's full-back on the flank a FLANK_EXPOSED pattern attacks, else None."""
    if pattern.kind is not PatternKind.FLANK_EXPOSED or pattern.channel is Channel.CENTRE:
        return None
    defenders = _team(metadata, pattern.opponent_id).players_in(Position.DEFENDER)
    index = RIGHT_BACK_INDEX if opposite_flank(pattern.channel) is Channel.RIGHT else LEFT_BACK_INDEX
    return defenders[index] if index < len(defenders) else None


def _team(metadata: MatchMetadata, team_id: str) -> Team:
    return metadata.home if metadata.home.team_id == team_id else metadata.away


def flank_label(pattern: TacticalPattern, opponent_name: str) -> str:
    """Where the pattern happens, named from the suffering side's point of view for entry patterns."""
    if pattern.kind is PatternKind.TURNOVER_ZONE:
        return ZONE_LABEL.format(third=pattern.third.value, channel=pattern.channel.value)
    if pattern.channel is Channel.CENTRE:
        return CENTRE_LABEL.format(opponent=opponent_name)
    return FLANK_LABEL.format(opponent=opponent_name, flank=opposite_flank(pattern.channel).value)


def tactical_evidence(pattern: TacticalPattern, metadata: MatchMetadata) -> TacticalEvidence:
    """Build the documented fact set and player list for a tactical_pattern moment."""
    team, opponent = _team(metadata, pattern.team_id).name, _team(metadata, pattern.opponent_id).name
    defender = exposed_defender(pattern, metadata)
    label = flank_label(pattern, opponent)
    share = round(pattern.share * PERCENT)
    window = int(pattern.window_s // SECONDS_PER_MINUTE)
    values = {"team": team, "defender": defender.name if defender else None, "flank_label": label,
              "count": pattern.count, "total": pattern.total, "share": share, "window": window,
              "channel": pattern.channel.value, "third": pattern.third.value}
    template = {PatternKind.FLANK_EXPOSED: FLANK_EXPOSED_SUMMARY, PatternKind.CHANNEL_OVERLOAD: CHANNEL_OVERLOAD_SUMMARY,
                PatternKind.TURNOVER_ZONE: TURNOVER_ZONE_SUMMARY}[pattern.kind]
    facts: dict[str, FactValue] = {
        "pattern": pattern.kind.value, "team": team, "opponent": opponent, "channel": pattern.channel.value,
        "third": pattern.third.value, "count": pattern.count, "total": pattern.total, "share_pct": share,
        "window_minutes": window, "defender": values["defender"], "flank_label": label,
        "summary": template.format(**values),
    }
    return TacticalEvidence(facts, (defender.player_id,) if defender else ())
