"""Tests for the evaluation report built from produced broadcasts and recaps.

Broadcasts come from an offline service over a seeded match, so the report is checked without any model.
They verify per-role counts, source rates, fact-check verdict tallies, and the persona samples.
"""

import asyncio

from test_live import GOALS_SEED, OFFLINE_POLICY, _offline_suite

from insidegame.agents.personas import PersonaKey
from insidegame.agents.recap_context import RecapStage
from insidegame.evaluation.report import summarize
from insidegame.live.segments import build_segment_profile
from insidegame.orchestration.cues import MomentBroadcast
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

MOMENTS = 3


def _report() -> tuple[list[MomentBroadcast], dict[str, object]]:
    async def scenario() -> tuple[list[MomentBroadcast], dict[str, object]]:
        result = simulate_match(build_fixture("brookhaven", "silverlake", GOALS_SEED))
        viewers = [build_segment_profile(PersonaKey.ANALYST.value),
                   build_segment_profile(PersonaKey.CASUAL.value, "es")]
        service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, viewers)
        broadcasts: list[MomentBroadcast] = []
        for event in result.events:
            for job in service.interpret(event).jobs:
                if len(broadcasts) < MOMENTS:
                    broadcasts.append(await service.produce(job))
        recap = await service.recap(RecapStage.FULL_TIME)
        return broadcasts, summarize(broadcasts, [recap])

    return asyncio.run(scenario())


def test_report_counts_every_role_and_tallies_fact_checks() -> None:
    broadcasts, report = _report()
    roles = report["roles"]
    assert report["broadcasts"] == MOMENTS
    assert roles["analyst"]["calls"] == roles["narrator"]["calls"] == MOMENTS  # type: ignore[index]
    assert roles["editor"]["calls"] == 1  # type: ignore[index]
    cue_count = sum(len(b.cues) for b in broadcasts)
    assert roles["card"]["calls"] == cue_count  # type: ignore[index]
    assert sum(report["fact_checks"].values()) == cue_count  # type: ignore[attr-defined]
    assert report["fact_check_issues"] == []


def test_offline_outputs_are_reported_as_fallbacks_with_samples() -> None:
    _, report = _report()
    assert report["roles"]["analyst"]["fallback_rate"] == 1.0  # type: ignore[index]
    samples = report["samples"]
    assert len(samples) == MOMENTS and all(s["cards"] for s in samples)  # type: ignore[union-attr]
