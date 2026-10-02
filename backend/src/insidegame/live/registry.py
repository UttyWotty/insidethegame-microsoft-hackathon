"""Registry of live match sessions: creates, looks up, and shuts down sessions.

Each session simulates its fixture up front and replays it in a background task.
The registry caps concurrent sessions, evicting finished ones first.
"""

import asyncio
import uuid

from insidegame.agents.factory import AgentSuite
from insidegame.agents.runner import RunPolicy
from insidegame.core.exceptions import SessionLimitError, SessionNotFoundError
from insidegame.live.pacing import MAX_SPEED, MIN_SPEED
from insidegame.live.session import MatchSession, SessionStatus, Sleeper
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

MAX_SESSIONS: int = 20
SESSION_ID_LENGTH: int = 8


class SessionRegistry:
    """In-memory store of live sessions sharing one agent suite."""

    def __init__(self, suite: AgentSuite, policy: RunPolicy, sleep: Sleeper = asyncio.sleep) -> None:
        """Create a registry; sleep defaults to asyncio.sleep and is injectable for tests."""
        self.suite, self.policy, self.sleep = suite, policy, sleep
        self.sessions: dict[str, MatchSession] = {}
        self.runners: dict[str, asyncio.Task[None]] = {}

    def _make_room(self) -> None:
        if len(self.sessions) < MAX_SESSIONS:
            return
        finished = [sid for sid, s in self.sessions.items() if s.status is SessionStatus.FINISHED]
        if not finished:
            raise SessionLimitError(f"At most {MAX_SESSIONS} live sessions are allowed")
        self.sessions.pop(finished[0])
        self.runners.pop(finished[0], None)

    def create(self, home: str, away: str, seed: int, speed: float) -> MatchSession:
        """Simulate a fixture and start replaying it."""
        self._make_room()
        result = simulate_match(build_fixture(home, away, seed))
        service = MatchIntelligenceService(result.metadata, self.suite, self.policy, viewers=())
        session_id = f"{result.metadata.match_id}-{uuid.uuid4().hex[:SESSION_ID_LENGTH]}"
        bounded_speed = min(max(speed, MIN_SPEED), MAX_SPEED)
        session = MatchSession(session_id, result, service, bounded_speed, self.sleep)
        self.sessions[session_id] = session
        self.runners[session_id] = asyncio.create_task(session.run())
        return session

    def get(self, session_id: str) -> MatchSession:
        """Return a session or raise SessionNotFoundError."""
        if session_id not in self.sessions:
            raise SessionNotFoundError(f"Unknown session {session_id!r}")
        return self.sessions[session_id]

    async def shutdown(self) -> None:
        """Cancel every running replay."""
        for task in self.runners.values():
            task.cancel()
        await asyncio.gather(*self.runners.values(), return_exceptions=True)
