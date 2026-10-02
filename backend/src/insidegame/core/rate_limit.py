"""Pure sliding-window rate limiter keyed by an arbitrary string.

Callers pass the current time, so the limiter has no clock or I/O and is deterministic under test.
It protects model-backed endpoints from runaway cost on a public deployment.
"""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class SlidingWindowLimiter:
    """Allows at most max_events per key within any window_s seconds."""

    max_events: int
    window_s: float
    events: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, key: str, now: float) -> bool:
        """Record and allow the event if the key is under its limit, otherwise reject it."""
        window = self.events.setdefault(key, deque())
        while window and window[0] <= now - self.window_s:
            window.popleft()
        if len(window) >= self.max_events:
            return False
        window.append(now)
        return True

    def retry_after(self, key: str, now: float) -> float:
        """Seconds until the key may send again, 0 when it is under its limit."""
        window = self.events.get(key)
        if not window or len(window) < self.max_events:
            return 0.0
        return max(0.0, window[0] + self.window_s - now)
