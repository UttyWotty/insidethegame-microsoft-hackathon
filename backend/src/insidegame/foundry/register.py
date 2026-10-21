"""Command-line adapter that registers (or updates) the hosted agent in a Foundry project and optionally chats with it.

Usage: python -m insidegame.foundry.register [--ask "Who is on top in the live match?"]
Reads the project endpoint, model deployment, MCP URL, and MCP key connection from the environment (set by azd).
"""

import argparse
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from insidegame.core.exceptions import ModelConfigError
from insidegame.foundry.definition import AGENT_NAME, HostedAgentSettings, build_agent_definition

AZURE_AI_PROJECT_ENDPOINT: str = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
AZURE_MODEL_DEPLOYMENT: str = os.getenv("AZURE_MODEL_DEPLOYMENT", "gpt-4.1-mini")
SERVICE_WEB_URI: str = os.getenv("SERVICE_WEB_URI", "")
AZURE_MCP_CONNECTION_ID: str = os.getenv("AZURE_MCP_CONNECTION_ID", "")
AGENT_DESCRIPTION: str = "Answers questions about live synthetic football matches through the Inside the Game MCP server."
AGENT_REFERENCE_TYPE: str = "agent_reference"


def _settings() -> HostedAgentSettings:
    if not AZURE_AI_PROJECT_ENDPOINT or not SERVICE_WEB_URI:
        raise ModelConfigError("AZURE_AI_PROJECT_ENDPOINT and SERVICE_WEB_URI must be set (run azd up first)")
    return HostedAgentSettings(AZURE_MODEL_DEPLOYMENT, f"{SERVICE_WEB_URI.rstrip('/')}/mcp/", AZURE_MCP_CONNECTION_ID)


def main() -> None:
    """Register the hosted agent, then optionally ask it one question."""
    parser = argparse.ArgumentParser(description="Register the Inside the Game hosted agent in Microsoft Foundry.")
    parser.add_argument("--ask", default="", help="Optional question to send to the agent after registering it.")
    args = parser.parse_args()
    client = AIProjectClient(endpoint=AZURE_AI_PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    agent = client.agents.create_version(agent_name=AGENT_NAME, definition=build_agent_definition(_settings()),
                                         description=AGENT_DESCRIPTION)
    print(f"Registered {agent.name} version {agent.version}")
    if args.ask:
        with client.get_openai_client() as openai_client:
            response = openai_client.responses.create(
                input=args.ask, extra_body={"agent": {"name": agent.name, "type": AGENT_REFERENCE_TYPE}})
            print(response.output_text)


if __name__ == "__main__":
    main()
