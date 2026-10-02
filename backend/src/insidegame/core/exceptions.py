"""Domain-specific exception hierarchy for the insidegame backend.

Every raised error derives from InsideGameError so callers can catch project errors precisely.
Each subclass names the layer or concern that failed.
"""


class InsideGameError(Exception):
    """Base class for all insidegame errors."""


class RosterError(InsideGameError):
    """Raised when a team roster is missing required players or is malformed."""


class FixtureError(InsideGameError):
    """Raised when a fixture references unknown clubs or invalid parameters."""


class SimulationError(InsideGameError):
    """Raised when the match simulator reaches an invalid state."""


class PersonaConfigError(InsideGameError):
    """Raised when a viewer profile is missing settings its persona requires."""


class AgentOutputError(InsideGameError):
    """Raised when an agent response cannot be parsed or fails validation."""


class ModelConfigError(InsideGameError):
    """Raised when the model client configuration is invalid or incomplete."""
