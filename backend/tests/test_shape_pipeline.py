"""Pipeline tests for team shape: MatchIntelligenceService.interpret feeds tracked positions into the analyzer.

They replay the demo match through the service, as the live session does, and check that both teams have a shape
reading with a block label by 20 minutes into each half, and that shape_shift moments reach the per-event update and
the snapshot. They also check the studio shape payload built from the same analyzer.
"""

from dataclasses import dataclass

import pytest
from fakes import CallbackChatClient

from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.runner import RunPolicy
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED, build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS

POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
READING_BY_S = 1200.0
BLOCKS = {"high", "mid", "low"}


@dataclass(frozen=True)
class ServedMatch:
    """Snapshots taken 20 minutes into each half, the per-event update dicts, and the service."""

    snapshots: dict[int, dict[str, object]]
    updates: list[dict[str, object]]
    service: MatchIntelligenceService


@pytest.fixture(scope="module")
def served() -> ServedMatch:
    result = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, DEMO_SEED))
    suite = create_agent_suite(CallbackChatClient(lambda instructions, prompt: "unused"))
    service = MatchIntelligenceService(result.metadata, suite, POLICY, [ViewerProfile("a", PersonaKey.ANALYST)])
    period_start: dict[int, float] = {}
    snapshots: dict[int, dict[str, object]] = {}
    updates = []
    for index, event in enumerate(result.events):
        upcoming = result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS]
        updates.append(service.interpret(event, upcoming).update.to_dict())
        start = period_start.setdefault(event.period, event.match_second)
        if event.period not in snapshots and event.match_second - start >= READING_BY_S:
            snapshots[event.period] = service.analyzer.snapshot()
    return ServedMatch(snapshots, updates, service)


def test_both_teams_have_a_shape_reading_by_twenty_minutes_into_each_half(served: ServedMatch) -> None:
    assert set(served.snapshots) == {1, 2}
    for snapshot in served.snapshots.values():
        shape = snapshot["shape"]
        assert isinstance(shape, dict) and set(shape) == {"home", "away"}
        for reading in shape.values():
            assert reading is not None and reading["block"] in BLOCKS
            assert {"line_height_m", "length_m", "width_m", "compactness_m", "samples", "window_minutes"} <= set(reading)


def test_shape_shift_moments_reach_the_update_and_the_snapshot(served: ServedMatch) -> None:
    raised = [m for update in served.updates for m in update["moments"]  # type: ignore[attr-defined]
              if m["kind"] == MomentKind.SHAPE_SHIFT.value]
    assert raised
    for moment in raised:
        update = next(u for u in served.updates if moment in u["moments"])  # type: ignore[operator]
        assert moment["event_ids"] == [update["event"]["event_id"]]  # type: ignore[index]
    snapshot_ids = {m["moment_id"] for m in served.service.analyzer.snapshot()["moments"]}  # type: ignore[union-attr]
    assert {m["moment_id"] for m in raised} <= snapshot_ids


def test_shape_studio_covers_the_whole_match(served: ServedMatch) -> None:
    studio = served.service.analyzer.shape_studio()
    timeline, shifts = studio["timeline"], studio["shifts"]
    assert isinstance(timeline, list) and isinstance(shifts, list)
    assert {p["period"] for p in timeline} == {1, 2} and timeline[0]["minute"] == 1
    assert any(p["home_line_m"] is not None and p["away_line_m"] is not None for p in timeline)
    assert shifts and set(shifts[0]) == {"moment_id", "minute_label", "period", "match_second", "team_id",
                                         "direction", "line_before_m", "line_after_m"}
