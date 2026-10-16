"""Pure live trace of one moment's multi-agent workflow: which agent ran when, and what it produced.

Workflow executor events (invoked, completed, failed) are folded into one step per agent with start and end times
relative to when the moment entered production. Once the broadcast exists, each step gains a short outcome read
from the cue provenance: model or template source, attempts, and the Standards Editor's verdicts.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

MS_PER_SECOND: float = 1000.0
INVOKED: str = "executor_invoked"
COMPLETED: str = "executor_completed"
FAILED: str = "executor_failed"
AGENTS: dict[str, str] = {
    "intake": "Intake", "analyst": "Match Analyst", "narrator": "Lead Commentator",
    "personalizer": "Personalization Producer", "fact_checker": "Standards Editor", "assembler": "Broadcast Translator",
    "scout": "Tactical Scout",
}
HANDOFFS: tuple[tuple[str, str], ...] = (
    ("intake", "analyst"), ("analyst", "narrator"), ("analyst", "personalizer"), ("narrator", "fact_checker"),
    ("personalizer", "fact_checker"), ("fact_checker", "assembler"), ("intake", "scout"), ("scout", "narrator"),
    ("scout", "personalizer"),
)
NOTHING_TO_CHECK: str = "nothing to check (templates)"
MODEL_SOURCES: frozenset[str] = frozenset({"model", "model_retry"})


class StepStatus(StrEnum):
    """Where an agent is in its work for this moment."""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TraceStep:
    """One agent's work on a moment, in milliseconds since the moment entered production."""

    executor_id: str
    status: StepStatus
    started_ms: int
    ended_ms: int | None = None


@dataclass
class AgentTrace:
    """The live trace of one moment's workflow."""

    moment_id: str
    minute: str
    kind: str
    origin_s: float
    steps: dict[str, TraceStep] = field(default_factory=dict)

    def observe(self, executor_id: str, event_type: str, now_s: float) -> None:
        """Fold one executor event at monotonic time now_s into the trace; unknown executors are ignored."""
        if executor_id not in AGENTS:
            return
        at = int((now_s - self.origin_s) * MS_PER_SECOND)
        step = self.steps.get(executor_id)
        if event_type == INVOKED and step is None:
            self.steps[executor_id] = TraceStep(executor_id, StepStatus.RUNNING, at)
        elif step is not None and event_type in (COMPLETED, FAILED):
            step.status = StepStatus.DONE if event_type == COMPLETED else StepStatus.FAILED
            step.ended_ms = at

    def to_dict(self, now_s: float, cues: Sequence[dict[str, object]]) -> dict[str, object]:
        """JSON-friendly trace with elapsed time, ordered steps, outcomes from cues, and the handoff edges."""
        notes = step_notes(cues)
        steps = [{"executor_id": s.executor_id, "agent": AGENTS[s.executor_id], "status": s.status.value,
                  "started_ms": s.started_ms, "ended_ms": s.ended_ms, "note": notes.get(s.executor_id, "")}
                 for s in sorted(self.steps.values(), key=lambda s: s.started_ms)]
        finished = all(s.status is not StepStatus.RUNNING for s in self.steps.values()) and bool(cues)
        elapsed = max((s.ended_ms or 0 for s in self.steps.values()), default=0) if finished else int(
            (now_s - self.origin_s) * MS_PER_SECOND)
        return {"moment_id": self.moment_id, "minute": self.minute, "kind": self.kind, "finished": finished,
                "elapsed_ms": elapsed, "steps": steps, "handoffs": [list(h) for h in HANDOFFS]}


def _source_note(entries: Sequence[dict[str, object]]) -> str:
    if not entries:
        return ""
    model = sum(str(e.get("source")) in MODEL_SOURCES for e in entries)
    attempts = max(int(str(e.get("attempts", 0))) for e in entries)
    if len(entries) == 1:
        return f"{'AI' if model else 'Template'}, {attempts} attempt{'s' if attempts != 1 else ''}"
    return f"{len(entries)} outputs: {model} AI, {len(entries) - model} template"


def step_notes(cues: Sequence[dict[str, object]]) -> dict[str, str]:
    """Short outcome per executor from the cues' provenance (empty until the broadcast exists)."""
    def role(name: str) -> list[dict[str, object]]:
        found = []
        for cue in cues:
            provenance = cue.get("provenance")
            entry = provenance.get(name) if isinstance(provenance, dict) else None
            if isinstance(entry, dict):
                found.append(entry)
        return found

    verdicts: Counter[str] = Counter(str(e.get("verdict")) for e in role("fact_check"))
    commentary_check = role("commentary_check")
    if commentary_check:
        verdicts[str(commentary_check[0].get("verdict"))] += 1
    verdicts.pop("skipped", None)
    translations = role("translation")
    return {
        "intake": f"{len(cues)} audience{'s' if len(cues) != 1 else ''}" if cues else "",
        "analyst": _source_note(role("explanation")[:1]),
        "scout": _source_note(role("explanation")[:1]),
        "narrator": _source_note(role("commentary")[:1]),
        "personalizer": _source_note(role("card")),
        "fact_checker": ", ".join(f"{n} {v}" for v, n in sorted(verdicts.items()))
        or (NOTHING_TO_CHECK if cues else ""),
        "assembler": f"{len(translations)} translated" if translations else ("English only" if cues else ""),
    }
