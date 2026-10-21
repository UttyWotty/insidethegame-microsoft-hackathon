"""Tests for the pure Foundry hosted agent definition.

They check the MCP tool wiring, the read-only tool allow-list, and the optional key connection (never a header).
No Azure calls are made.
"""

import pytest

pytest.importorskip("azure.ai.projects")

from insidegame.foundry.definition import (  # noqa: E402
    ALLOWED_TOOLS,
    MCP_SERVER_LABEL,
    HostedAgentSettings,
    build_agent_definition,
)

MCP_URL = "https://example.azurecontainerapps.io/mcp/"


def test_definition_points_the_mcp_tool_at_the_deployed_server() -> None:
    definition = build_agent_definition(HostedAgentSettings("gpt-4.1-mini", MCP_URL))
    tool = definition.tools[0]
    assert definition.model == "gpt-4.1-mini"
    assert tool.server_url == MCP_URL and tool.server_label == MCP_SERVER_LABEL
    assert tool.headers is None and tool.project_connection_id is None


def test_agent_cannot_start_matches_and_uses_the_key_connection_when_configured() -> None:
    connection = "/subscriptions/s/resourceGroups/g/providers/Microsoft.CognitiveServices/accounts/a/projects/p/connections/c"
    definition = build_agent_definition(HostedAgentSettings("m", MCP_URL, connection))
    tool = definition.tools[0]
    assert "start_match" not in tool.allowed_tools and set(tool.allowed_tools) == set(ALLOWED_TOOLS)
    assert tool.project_connection_id == connection and tool.headers is None


def test_agent_can_read_the_threat_leaderboard() -> None:
    assert "get_threat_leaderboard" in ALLOWED_TOOLS
    tool = build_agent_definition(HostedAgentSettings("m", MCP_URL)).tools[0]
    assert "get_threat_leaderboard" in tool.allowed_tools


def test_agent_can_read_team_shape() -> None:
    assert "get_team_shape" in ALLOWED_TOOLS
    tool = build_agent_definition(HostedAgentSettings("m", MCP_URL)).tools[0]
    assert "get_team_shape" in tool.allowed_tools
