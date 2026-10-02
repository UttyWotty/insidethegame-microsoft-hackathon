"""Creates the suite of specialised Agent Framework agents from an injected chat client.

The same factory serves local development and cloud deployment because the client is supplied by an adapter.
Each agent has a single role defined by its instructions in prompts.py.
"""

from dataclasses import dataclass

from agent_framework import Agent, SupportsChatGetResponse

from insidegame.agents.prompts import (
    ANALYST_INSTRUCTIONS,
    COMPANION_INSTRUCTIONS,
    FACT_CHECKER_INSTRUCTIONS,
    NARRATOR_INSTRUCTIONS,
    PERSONALIZER_INSTRUCTIONS,
    RECAP_INSTRUCTIONS,
    TRANSLATOR_INSTRUCTIONS,
)


@dataclass(frozen=True)
class AgentSuite:
    """The seven specialised agents: the moment and recap pipeline, its fact-checker, and the viewer companion."""

    analyst: Agent
    narrator: Agent
    personalizer: Agent
    translator: Agent
    editor: Agent
    companion: Agent
    fact_checker: Agent


def create_agent_suite(client: SupportsChatGetResponse) -> AgentSuite:
    """Build every agent on top of one chat client."""
    return AgentSuite(
        analyst=Agent(client, ANALYST_INSTRUCTIONS, name="match_analyst",
                      description="Explains why key moments matter, using statistics tools."),
        narrator=Agent(client, NARRATOR_INSTRUCTIONS, name="lead_commentator",
                       description="Writes broadcast-ready commentary lines."),
        personalizer=Agent(client, PERSONALIZER_INSTRUCTIONS, name="personalization_producer",
                           description="Tailors explanations to each viewer persona."),
        translator=Agent(client, TRANSLATOR_INSTRUCTIONS, name="broadcast_translator",
                         description="Localises persona cards for global markets."),
        editor=Agent(client, RECAP_INSTRUCTIONS, name="match_editor",
                     description="Writes automated half-time and full-time recaps."),
        companion=Agent(client, COMPANION_INSTRUCTIONS, name="match_companion",
                        description="Answers viewers' questions about the live match, using statistics tools."),
        fact_checker=Agent(client, FACT_CHECKER_INSTRUCTIONS, name="standards_editor",
                           description="Fact-checks cards and commentary before they go to air."),
    )
