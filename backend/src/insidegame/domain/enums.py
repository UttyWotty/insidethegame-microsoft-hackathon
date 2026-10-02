"""Enumerations shared across the match event domain.

They define team sides, player positions, event types, and event outcomes.
String values are stable and form part of the public machine-readable event contract.
"""

from enum import StrEnum


class Side(StrEnum):
    """Which side of the fixture a team plays on."""

    HOME = "home"
    AWAY = "away"

    @property
    def opponent(self) -> "Side":
        """Return the opposing side."""
        return Side.AWAY if self is Side.HOME else Side.HOME


class Position(StrEnum):
    """Broad playing position of a player."""

    GOALKEEPER = "GK"
    DEFENDER = "DF"
    MIDFIELDER = "MF"
    FORWARD = "FW"


class EventType(StrEnum):
    """Kinds of match events emitted by the simulator."""

    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
    KICK_OFF = "kick_off"
    PASS = "pass"
    CARRY = "carry"
    SHOT = "shot"
    GOAL = "goal"
    SAVE = "save"
    PRESSURE = "pressure"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    FOUL = "foul"
    POSSESSION_CHANGE = "possession_change"


class Outcome(StrEnum):
    """Whether an action achieved its intent."""

    SUCCESS = "success"
    FAILURE = "failure"


class ShotResult(StrEnum):
    """Final result of a shot attempt."""

    GOAL = "goal"
    SAVED = "saved"
    OFF_TARGET = "off_target"
    BLOCKED = "blocked"
