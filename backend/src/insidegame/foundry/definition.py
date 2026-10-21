"""Pure construction of the Foundry hosted agent definition that uses the project's MCP server as its tool.

The hosted agent answers questions about live synthetic matches by calling the MCP tools exposed at /mcp.
Only read and question tools are allowed, so a portal user cannot start unbounded numbers of matches.
"""

from dataclasses import dataclass

from azure.ai.projects.models import MCPTool, PromptAgentDefinition

AGENT_NAME: str = "inside-the-game-companion"
MCP_SERVER_LABEL: str = "inside_the_game"
APPROVAL_NEVER: str = "never"
ALLOWED_TOOLS: tuple[str, ...] = (
    "list_matches", "get_match_state", "get_key_moments", "get_player_stats", "get_recaps", "ask_match_companion",
    "get_threat_leaderboard", "get_team_shape",
)
INSTRUCTIONS: str = (
    "You are the Inside the Game match companion for broadcasters and fans. Live synthetic football matches are "
    "available through the inside_the_game tools. Call list_matches to find a session, then use get_match_state, "
    "get_key_moments, get_player_stats, get_threat_leaderboard, get_team_shape, and get_recaps for facts, or "
    "ask_match_companion for a persona-specific "
    "answer. Only state numbers returned by the tools, and say clearly when no match is live. All clubs and players "
    "are fictional."
)


@dataclass(frozen=True)
class HostedAgentSettings:
    """Inputs for the hosted agent definition.

    Defaults: mcp_connection_id is empty, meaning the MCP endpoint is called without authentication. Otherwise it is
    the resource id of a Foundry project connection (Custom keys, key Authorization = "Bearer <MCP_API_KEY>"), since
    Foundry refuses secrets in the MCP tool's headers.
    """

    model_deployment: str
    mcp_server_url: str
    mcp_connection_id: str = ""


def build_agent_definition(settings: HostedAgentSettings) -> PromptAgentDefinition:
    """Return the prompt agent definition with the MCP tool restricted to read and question tools."""
    tool = MCPTool(
        server_label=MCP_SERVER_LABEL, server_url=settings.mcp_server_url, allowed_tools=list(ALLOWED_TOOLS),
        require_approval=APPROVAL_NEVER, project_connection_id=settings.mcp_connection_id or None,
    )
    return PromptAgentDefinition(model=settings.model_deployment, instructions=INSTRUCTIONS, tools=[tool])
