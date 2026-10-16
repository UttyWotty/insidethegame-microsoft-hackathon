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


class SessionNotFoundError(InsideGameError):
    """Raised when a live match session id is unknown."""


class SessionLimitError(InsideGameError):
    """Raised when the maximum number of concurrent live sessions is reached."""


class RateLimitError(InsideGameError):
    """Raised when a caller exceeds the allowed request rate for a model-backed operation."""


class SpeechUnavailableError(InsideGameError):
    """Raised when spoken audio is requested but no speech service is configured or it failed."""


class LineNotFoundError(InsideGameError):
    """Raised when a spoken line is requested that the match session did not produce or no longer holds."""


class HighlightsNotReadyError(InsideGameError):
    """Raised when a highlights reel is requested before the match has reached that recap stage."""


class XtConvergenceError(InsideGameError):
    """Raised when expected threat (xT) value iteration does not converge within its iteration budget."""
