"""Tests for the live agent trace of a moment's workflow.

They check that executor events become timed steps, that unknown executors are ignored, and that outcomes are
summarised from cue provenance. All logic is pure.
"""

from insidegame.orchestration.trace import (
    COMPLETED,
    FAILED,
    HANDOFFS,
    INVOKED,
    NOTHING_TO_CHECK,
    AgentTrace,
    step_notes,
)


def _cue(card_source: str, verdict: str) -> dict[str, object]:
    return {"provenance": {"explanation": {"source": "model", "attempts": 1},
                           "commentary": {"source": "model_retry", "attempts": 2},
                           "card": {"source": card_source, "attempts": 1},
                           "fact_check": {"verdict": verdict}, "commentary_check": {"verdict": "approved"}}}


def test_executor_events_become_timed_steps() -> None:
    trace = AgentTrace("m1", "23'", "goal", origin_s=100.0)
    trace.observe("analyst", INVOKED, 100.5)
    trace.observe("analyst", COMPLETED, 102.0)
    trace.observe("narrator", INVOKED, 102.1)
    trace.observe("not_an_agent", INVOKED, 102.1)
    live = trace.to_dict(103.0, [])
    assert [s["executor_id"] for s in live["steps"]] == ["analyst", "narrator"]
    assert live["steps"][0]["started_ms"] == 500 and live["steps"][0]["ended_ms"] == 2000
    assert live["steps"][1]["status"] == "running" and not live["finished"] and live["elapsed_ms"] == 3000
    trace.observe("narrator", FAILED, 104.0)
    done = trace.to_dict(110.0, [_cue("model", "approved")])
    assert done["finished"] and done["elapsed_ms"] == 4000 and done["steps"][1]["status"] == "failed"
    assert len(done["handoffs"]) == len(HANDOFFS)


def test_outcomes_are_read_from_cue_provenance() -> None:
    notes = step_notes([_cue("model", "approved"), _cue("fallback", "revised")])
    assert notes["analyst"] == "AI, 1 attempt" and notes["narrator"] == "AI, 2 attempts"
    assert notes["personalizer"] == "2 outputs: 1 AI, 1 template"
    assert notes["fact_checker"] == "2 approved, 1 revised" and notes["intake"] == "2 audiences"
    assert notes["assembler"] == "English only"
    assert step_notes([])["analyst"] == "" and step_notes([])["fact_checker"] == ""
    skipped = {"provenance": {"fact_check": {"verdict": "skipped"}, "commentary_check": {"verdict": "skipped"}}}
    assert step_notes([skipped])["fact_checker"] == NOTHING_TO_CHECK


def test_scout_is_a_named_agent_with_its_handoffs_and_source_note() -> None:
    from insidegame.orchestration.trace import AGENTS
    assert AGENTS["scout"] == "Tactical Scout"
    assert {("intake", "scout"), ("scout", "narrator"), ("scout", "personalizer")} <= set(HANDOFFS)
    trace = AgentTrace("m2", "31'", "tactical_pattern", origin_s=0.0)
    trace.observe("scout", INVOKED, 0.1)
    trace.observe("scout", COMPLETED, 1.0)
    done = trace.to_dict(2.0, [_cue("model", "approved")])
    assert done["steps"][0]["agent"] == "Tactical Scout" and done["steps"][0]["note"] == "AI, 1 attempt"
    assert step_notes([])["scout"] == ""
