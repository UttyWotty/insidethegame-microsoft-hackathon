"""Builds the per-moment multi-agent workflow graph with Microsoft Agent Framework.

Graph: intake -> analyst -> (narrator || personalizer) -> assembler, with fan-out and fan-in edges.
Shared workflow state carries the job and explanation so the assembler can join parallel branches.
"""

from agent_framework import Workflow, WorkflowBuilder

from insidegame.agents.factory import AgentSuite
from insidegame.agents.runner import RunPolicy
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.orchestration.executors import (
    AnalystExecutor,
    AssemblerExecutor,
    IntakeExecutor,
    NarratorExecutor,
    PersonalizerExecutor,
)

WORKFLOW_NAME: str = "moment_intelligence"
WORKFLOW_DESCRIPTION: str = "Explains, narrates, personalizes, and translates one key moment into overlay cues."


def build_moment_workflow(suite: AgentSuite, analyzer: MatchAnalyzer, policy: RunPolicy) -> Workflow:
    """Wire the executors into the moment intelligence workflow."""
    intake, assembler = IntakeExecutor(), AssemblerExecutor(analyzer.metadata.match_id)
    analyst = AnalystExecutor(suite, analyzer, policy)
    narrator, personalizer = NarratorExecutor(suite, policy), PersonalizerExecutor(suite, policy)
    return (
        WorkflowBuilder(name=WORKFLOW_NAME, description=WORKFLOW_DESCRIPTION, start_executor=intake)
        .add_edge(intake, analyst)
        .add_fan_out_edges(analyst, [narrator, personalizer])
        .add_fan_in_edges([narrator, personalizer], assembler)
        .build()
    )
