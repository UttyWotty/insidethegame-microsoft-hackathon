"""Command-line evaluation run: simulate a match, push its key moments through the live agents, and report.

It uses the environment-configured model runtime, so the same command evaluates MLX, Ollama, or Foundry.
Usage: python -m insidegame.evaluation.run --max-moments 4 --output report.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from insidegame.adapters.model_client import build_model_runtime
from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey
from insidegame.agents.recap_context import RecapStage
from insidegame.evaluation.report import summarize
from insidegame.live.segments import build_segment_profile
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

DEFAULT_HOME: str = "kestrel_bay"
DEFAULT_AWAY: str = "ironvale"
DEFAULT_SEED: int = 7
DEFAULT_MAX_MOMENTS: int = 4
DEFAULT_TRANSLATION_LANGUAGE: str = "es"

logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the agent pipeline on a simulated match.")
    parser.add_argument("--home", default=DEFAULT_HOME)
    parser.add_argument("--away", default=DEFAULT_AWAY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-moments", type=int, default=DEFAULT_MAX_MOMENTS)
    parser.add_argument("--output", type=Path, default=None)
    return parser


async def evaluate(home: str, away: str, seed: int, max_moments: int) -> dict[str, object]:
    """Run the agents over the first max_moments broadcast moments and a full-time recap."""
    runtime = build_model_runtime()
    result = simulate_match(build_fixture(home, away, seed))
    home_team = result.metadata.home
    viewers = [
        build_segment_profile(PersonaKey.ANALYST.value),
        build_segment_profile(PersonaKey.CASUAL.value, DEFAULT_TRANSLATION_LANGUAGE),
        build_segment_profile(PersonaKey.SUPERFAN.value, team_id=home_team.team_id),
        build_segment_profile(PersonaKey.PLAYER_TRACKER.value, player_id=home_team.players[-2].player_id),
        build_segment_profile(PersonaKey.NEWCOMER.value),
    ]
    service = MatchIntelligenceService(result.metadata, create_agent_suite(runtime.client), runtime.policy, viewers)
    broadcasts = []
    for event in result.events:
        for job in service.interpret(event).jobs:
            if len(broadcasts) < max_moments:
                logger.info("Producing %s at %s", job.context.moment.kind.value, job.context.moment.minute_label)
                broadcasts.append(await service.produce(job))
    recap = await service.recap(RecapStage.FULL_TIME)
    report = summarize(broadcasts, [recap])
    report["provider"] = runtime.provider.value
    return report


def main() -> None:
    """Parse arguments, run the evaluation, and print or save the report."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parser().parse_args()
    report = asyncio.run(evaluate(args.home, args.away, args.seed, args.max_moments))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
