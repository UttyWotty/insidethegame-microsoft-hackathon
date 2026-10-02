"""Pure helpers that pick which player is involved in a simulated action.

Receivers are chosen by the target zone of a pass and defenders by the zone where the ball is.
Zone weights per position approximate where each line of a 4-3-3 typically operates.
"""

import random

from insidegame.core.exceptions import RosterError
from insidegame.domain.enums import Position
from insidegame.domain.teams import Player, Team

DEFENSIVE_THIRD_END_M: float = 35.0
MIDDLE_THIRD_END_M: float = 70.0
GOALKEEPER_BACKPASS_ZONE_M: float = 20.0

ZoneWeights = dict[Position, float]

RECEIVER_WEIGHTS: tuple[ZoneWeights, ZoneWeights, ZoneWeights] = (
    {Position.GOALKEEPER: 0.10, Position.DEFENDER: 0.55, Position.MIDFIELDER: 0.35},
    {Position.DEFENDER: 0.25, Position.MIDFIELDER: 0.55, Position.FORWARD: 0.20},
    {Position.MIDFIELDER: 0.40, Position.FORWARD: 0.60},
)
DEFENDER_WEIGHTS: tuple[ZoneWeights, ZoneWeights, ZoneWeights] = (
    {Position.MIDFIELDER: 0.45, Position.FORWARD: 0.55},
    {Position.DEFENDER: 0.25, Position.MIDFIELDER: 0.60, Position.FORWARD: 0.15},
    {Position.DEFENDER: 0.70, Position.MIDFIELDER: 0.30},
)


def _zone_index(x: float) -> int:
    if x < DEFENSIVE_THIRD_END_M:
        return 0
    return 1 if x < MIDDLE_THIRD_END_M else 2


def _weighted_pick(candidates: list[Player], weights: ZoneWeights, rng: random.Random) -> Player:
    scored = [(p, weights.get(p.position, 0.0)) for p in candidates]
    scored = [(p, w) for p, w in scored if w > 0.0]
    if not scored:
        raise RosterError("No eligible player for the requested zone")
    players, player_weights = zip(*scored, strict=True)
    return rng.choices(players, weights=player_weights, k=1)[0]


def pick_receiver(team: Team, carrier: Player, target_x: float, rng: random.Random) -> Player:
    """Choose a teammate to receive a pass aimed at target_x (attacking frame)."""
    candidates = [p for p in team.players if p.player_id != carrier.player_id]
    if target_x >= GOALKEEPER_BACKPASS_ZONE_M:
        candidates = [p for p in candidates if p.position is not Position.GOALKEEPER]
    return _weighted_pick(candidates, RECEIVER_WEIGHTS[_zone_index(target_x)], rng)


def pick_defender(team: Team, ball_x_attacking_frame: float, rng: random.Random) -> Player:
    """Choose the defending player who engages the ball, given its x in the attacker's frame."""
    outfield = [p for p in team.players if p.position is not Position.GOALKEEPER]
    return _weighted_pick(outfield, DEFENDER_WEIGHTS[_zone_index(ball_x_attacking_frame)], rng)
