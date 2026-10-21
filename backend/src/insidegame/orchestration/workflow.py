"""Builds the per-moment multi-agent workflow graph with Microsoft Agent Framework.

Graph: intake -> analyst or scout (routed by moment kind) -> (narrator || personalizer) -> fact_checker -> assembler,
with conditional, fan-out, and fan-in edges.
Shared workflow state carries the job and explanation, so later stages can join the parallel branches.
"""

from agent_framework import Workflow, WorkflowBuilder

from insidegame.agents.factory import AgentSuite
from insidegame.agents.runner import RunPolicy
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.orchestration.executors import (
    AnalystExecutor,
    AssemblerExecutor,
    FactCheckerExecutor,
    IntakeExecutor,
    NarratorExecutor,
    PersonalizerExecutor,
    ScoutExecutor,
    is_not_tactical,
    is_tactical,
)

WORKFLOW_NAME: str = "moment_intelligence"
WORKFLOW_DESCRIPTION: str = "Explains (analyst or Tactical Scout), narrates, personalizes, fact-checks, and translates one key moment into overlay cues."


def build_moment_workflow(suite: AgentSuite, analyzer: MatchAnalyzer, policy: RunPolicy) -> Workflow:
    """Wire the executors into the moment intelligence workflow."""
    intake, assembler = IntakeExecutor(), AssemblerExecutor(analyzer.metadata.match_id, suite, policy)
    analyst, scout = AnalystExecutor(suite, analyzer, policy), ScoutExecutor(suite, analyzer, policy)
    narrator, personalizer = NarratorExecutor(suite, policy), PersonalizerExecutor(suite, policy)
    squad = {p.name for team in (analyzer.metadata.home, analyzer.metadata.away) for p in team.players}
    checker = FactCheckerExecutor(suite, squad, policy)
    return (
        WorkflowBuilder(name=WORKFLOW_NAME, description=WORKFLOW_DESCRIPTION, start_executor=intake)
        .add_edge(intake, analyst, condition=is_not_tactical)
        .add_edge(intake, scout, condition=is_tactical)
        .add_fan_out_edges(analyst, [narrator, personalizer])
        .add_fan_out_edges(scout, [narrator, personalizer])
        .add_fan_in_edges([narrator, personalizer], checker)
        .add_edge(checker, assembler)
        .build()
    )
