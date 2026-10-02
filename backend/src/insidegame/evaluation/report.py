"""Pure summarisation of agent outcomes into an evaluation report.

For each agent role it counts model, corrected, and fallback outputs, latency percentiles, and top rejection reasons.
Samples of persona cards are included so reviewers can judge tone and differentiation, not just rates.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from insidegame.agents.runner import AgentOutcome, OutputSource
from insidegame.agents.schemas import MatchRecap
from insidegame.orchestration.cues import MomentBroadcast

PERCENTILE_MEDIAN: float = 0.5
PERCENTILE_TAIL: float = 0.95
TOP_PROBLEMS: int = 3
PROBLEM_PREVIEW_CHARS: int = 120
SAMPLE_BROADCASTS: int = 3
RATE_DECIMALS: int = 3


@dataclass
class RoleStats:
    """Accumulated outcome statistics for one agent role."""

    sources: Counter[str] = field(default_factory=Counter)
    latencies_ms: list[int] = field(default_factory=list)
    problems: Counter[str] = field(default_factory=Counter)

    def add(self, source: str, latency_ms: int, problems: Sequence[str] = ()) -> None:
        """Record one outcome."""
        self.sources[source] += 1
        self.latencies_ms.append(latency_ms)
        self.problems.update(p[:PROBLEM_PREVIEW_CHARS] for p in problems)

    def to_dict(self) -> dict[str, object]:
        """Return rates, latency percentiles, and top problems."""
        total = sum(self.sources.values())
        ordered = sorted(self.latencies_ms)
        pick = (lambda q: ordered[min(int(q * len(ordered)), len(ordered) - 1)]) if ordered else (lambda q: 0)
        return {
            "calls": total,
            "model_rate": round(self.sources[OutputSource.MODEL.value] / total, RATE_DECIMALS) if total else 0.0,
            "corrected_rate": round(self.sources[OutputSource.MODEL_RETRY.value] / total, RATE_DECIMALS) if total else 0.0,
            "fallback_rate": round(self.sources[OutputSource.FALLBACK.value] / total, RATE_DECIMALS) if total else 0.0,
            "latency_p50_ms": pick(PERCENTILE_MEDIAN),
            "latency_p95_ms": pick(PERCENTILE_TAIL),
            "top_problems": self.problems.most_common(TOP_PROBLEMS),
        }


def _add_outcome(stats: dict[str, RoleStats], role: str, outcome: AgentOutcome) -> None:  # type: ignore[type-arg]
    stats.setdefault(role, RoleStats()).add(outcome.source.value, outcome.latency_ms, outcome.problems)


def summarize(broadcasts: Sequence[MomentBroadcast], recaps: Sequence[AgentOutcome[MatchRecap]]) -> dict[str, object]:
    """Build the evaluation report for a run."""
    stats: dict[str, RoleStats] = {}
    for broadcast in broadcasts:
        _add_outcome(stats, "analyst", broadcast.explanation)
        _add_outcome(stats, "narrator", broadcast.commentary)
        for cue in broadcast.cues:
            for role in ("card", "translation"):
                record = cue.provenance.get(role)
                if isinstance(record, dict):
                    stats.setdefault(role, RoleStats()).add(str(record["source"]), int(record["latency_ms"]))
    for recap in recaps:
        _add_outcome(stats, "editor", recap)
    samples = [{
        "minute": b.context.moment.minute_label, "kind": b.context.moment.kind.value,
        "explanation": b.explanation.value.model_dump(mode="json"), "commentary": b.commentary.value.line,
        "cards": {c.persona + ("" if c.language == "en" else f"/{c.language}"): {"title": c.title, "body": c.body}
                  for c in b.cues},
    } for b in broadcasts[:SAMPLE_BROADCASTS]]
    return {
        "broadcasts": len(broadcasts),
        "roles": {role: s.to_dict() for role, s in stats.items()},
        "samples": samples,
        "recaps": [r.value.model_dump(mode="json") for r in recaps],
    }
