"""Model Context Protocol server exposing live match intelligence as tools for external agents.

GitHub Copilot, Microsoft Foundry agents, or any MCP client can start matches, read live state and key moments,
look up players, rank the expected threat (xT) danger leaderboard, read recaps, and question the Match Companion;
tools share the API's live session registry.
"""

from collections.abc import Callable
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from insidegame.agents.context import build_viewer_context
from insidegame.agents.personas import DEFAULT_LANGUAGE
from insidegame.agents.question_context import build_question_context
from insidegame.agents.steps import answer_question
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.threat import XT_DECIMALS
from insidegame.analytics.threat_board import threat_leaders
from insidegame.live.pacing import DEFAULT_SPEED
from insidegame.live.registry import SessionRegistry
from insidegame.live.segments import fixture_segment_profile
from insidegame.simulation.roster import CLUB_PRESETS

SERVER_NAME: str = "inside-the-game"
SERVER_INSTRUCTIONS: str = (
    "Live, explainable football match intelligence on synthetic matches. Start a match with start_match, then "
    "read get_match_state, get_key_moments, get_player_stats, get_threat_leaderboard, and get_recaps, or ask "
    "ask_match_companion a question."
)
DEFAULT_MOMENTS: int = 5
MAX_MOMENTS: int = 30
DEFAULT_THREAT_LEADERS: int = 5
MAX_THREAT_LEADERS: int = 22
DEFAULT_PERSONA: str = "analyst"
MCP_CLIENT_KEY: str = "mcp"  # MCP callers share one creation budget; the endpoint is guarded by MCP_API_KEY

RegistryGetter = Callable[[], SessionRegistry]
# Every tool is async so it runs on the event loop that owns live sessions, never in a worker thread.


def threat_leaderboard(analyzer: MatchAnalyzer, limit: int) -> dict[str, object]:
    """Expected threat (xT) added per team and the top limit players by xT added."""
    teams = [{"team_id": team.team_id, "name": team.name,
              "xt_added": round(analyzer.stats.teams[team.team_id].xt_added, XT_DECIMALS),
              "line_breaking_passes": analyzer.stats.teams[team.team_id].line_breaking_passes}
             for team in (analyzer.metadata.home, analyzer.metadata.away)]
    players = threat_leaders(analyzer.stats.players.values(), limit)
    return {"teams": teams, "players": [leader.to_dict() for leader in players]}


def _register_session_tools(server: MCPServer, registry: RegistryGetter) -> None:
    """Tools that list clubs and start or list match sessions."""

    @server.tool(description="List the fictional clubs and their tactical styles.")
    async def list_clubs() -> list[dict[str, str]]:
        return [{"key": key, "name": p.name, "style": p.style.label} for key, p in CLUB_PRESETS.items()]

    @server.tool(description="Simulate a fixture and start its live replay; returns the session id.")
    async def start_match(
        home: Annotated[str, Field(description="Home club key from list_clubs.")],
        away: Annotated[str, Field(description="Away club key from list_clubs.")],
        seed: Annotated[int, Field(description="Simulation seed; the same seed replays the same match.")] = 7,
        speed: Annotated[float, Field(description="Match seconds per real second.")] = DEFAULT_SPEED,
    ) -> dict[str, object]:
        registry().check_create_rate(MCP_CLIENT_KEY)
        return registry().create(home, away, seed, speed).describe()

    @server.tool(description="List live and finished match sessions.")
    async def list_matches() -> list[dict[str, object]]:
        return [{"session_id": s.session_id, "status": s.status.value, "fixture": s.result.metadata.match_id}
                for s in registry().sessions.values()]


def _register_read_tools(server: MCPServer, registry: RegistryGetter) -> None:
    """Tools that read live match state, moments, player statistics, the danger leaderboard, and recaps."""

    @server.tool(description="Current score, clock, team statistics, rhythm, and standout players.")
    async def get_match_state(session_id: str) -> dict[str, object]:
        return build_question_context(registry().get(session_id).service.analyzer).to_prompt_dict()

    @server.tool(description="The most recent key moments with importance and supporting facts.")
    async def get_key_moments(
        session_id: str,
        limit: Annotated[int, Field(description="How many recent moments to return.", ge=1, le=MAX_MOMENTS)] = DEFAULT_MOMENTS,
    ) -> list[dict[str, object]]:
        moments = registry().get(session_id).service.analyzer.moments[-limit:]
        return [m.to_dict() for m in moments]

    @server.tool(description="Live statistics for one player, matched by full name.")
    async def get_player_stats(session_id: str, player_name: str) -> dict[str, object]:
        players = registry().get(session_id).service.analyzer.stats.players.values()
        match = next((p for p in players if p.name.lower() == player_name.lower()), None)
        return match.to_dict() | {"name": match.name} if match else {"error": f"Unknown player {player_name!r}"}

    @server.tool(description="Expected threat (xT) added by each team and the players whose passes and carries "
                             "added the most, with line-breaking passes.")
    async def get_threat_leaderboard(
        session_id: str,
        limit: Annotated[int, Field(description="How many players to return.", ge=1,
                                    le=MAX_THREAT_LEADERS)] = DEFAULT_THREAT_LEADERS,
    ) -> dict[str, object]:
        return threat_leaderboard(registry().get(session_id).service.analyzer, limit)

    @server.tool(description="Half-time and full-time recaps written so far by the Match Editor agent.")
    async def get_recaps(session_id: str) -> list[dict[str, object]]:
        return registry().get(session_id).recaps


def _register_companion_tool(server: MCPServer, registry: RegistryGetter) -> None:
    """The tool that questions the Match Companion agent."""

    @server.tool(description="Ask the Match Companion agent a question about the live match.")
    async def ask_match_companion(
        session_id: str,
        question: Annotated[str, Field(description="Question about this match.", min_length=3, max_length=300)],
        persona: Annotated[str, Field(description="analyst, casual, superfan, player_tracker, or newcomer.")] = DEFAULT_PERSONA,
        language: Annotated[str, Field(description="Answer language code, for example en or es.")] = DEFAULT_LANGUAGE,
        team: Annotated[str | None, Field(description="Favourite club team_id for the superfan persona.")] = None,
        player: Annotated[str | None, Field(description="Tracked player_id for the player_tracker persona.")] = None,
    ) -> dict[str, object]:
        reg = registry()
        analyzer = reg.get(session_id).service.analyzer
        profile = fixture_segment_profile(analyzer.metadata, persona, language, team, player)
        viewer = build_viewer_context(profile, analyzer.metadata)
        reg.check_ask_rate(session_id)
        outcome = await answer_question(reg.suite, question, build_question_context(analyzer), viewer, analyzer,
                                        reg.policy)
        return outcome.value.model_dump(mode="json") | {"source": outcome.source.value}


def build_mcp_server(registry: RegistryGetter) -> MCPServer:
    """Create the MCP server; registry is resolved per call because it is created at application startup."""
    server = MCPServer(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    _register_session_tools(server, registry)
    _register_read_tools(server, registry)
    _register_companion_tool(server, registry)
    return server
