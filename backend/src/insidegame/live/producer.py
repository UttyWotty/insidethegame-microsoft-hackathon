"""Producer desk: the human-in-the-loop record of what the agents produced and what went to air.

It keeps one record per broadcast moment (explanation, commentary, every audience's cue with provenance and
fact-check), can hold AI overlays for approval and release them, and summarises pipeline health for the console.
"""

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.analytics.moments import KeyMoment
from insidegame.orchestration.cues import MomentBroadcast

RATE_DECIMALS: int = 3
CUE_ROLES: tuple[str, ...] = ("explanation", "commentary", "card", "translation")


class AirStatus(StrEnum):
    """Whether a moment's overlays reached viewers."""

    AIRED = "aired"
    HELD = "held"
    RELEASED = "released"


@dataclass
class BroadcastRecord:
    """Everything produced for one moment, as the producer sees it."""

    moment_id: str
    minute: str
    kind: str
    importance: float
    explanation: dict[str, object]
    commentary: str
    degraded: bool
    status: AirStatus
    cues: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {**self.__dict__, "status": self.status.value}


@dataclass
class ProducerDesk:
    """Hold, release, and audit state for one live session."""

    hold: bool = False
    records: dict[str, BroadcastRecord] = field(default_factory=dict)

    def record(self, broadcast: MomentBroadcast) -> BroadcastRecord:
        """Register a produced moment; it is held when the desk is holding, otherwise it airs at once."""
        moment = broadcast.context.moment
        existing = self.records.get(moment.moment_id)
        cues = [cue.to_dict() for cue in broadcast.cues]
        if existing is not None:
            existing.cues.extend(cues)
            return existing
        record = BroadcastRecord(
            moment.moment_id, moment.minute_label, moment.kind.value, moment.importance,
            broadcast.explanation.value.model_dump(mode="json"), broadcast.commentary.value.line, broadcast.degraded,
            AirStatus.HELD if self.hold else AirStatus.AIRED, cues)
        self.records[moment.moment_id] = record
        return record

    def release(self, moment_id: str | None) -> list[dict[str, object]]:
        """Release one held moment, or every held moment when moment_id is None; returns cues to publish."""
        released: list[dict[str, object]] = []
        for record in self.records.values():
            if record.status is AirStatus.HELD and moment_id in (None, record.moment_id):
                record.status = AirStatus.RELEASED
                released.extend(record.cues)
        return released

    def summary(self, moments: list[KeyMoment], segments: int) -> dict[str, object]:
        """Timeline of all detected moments, broadcast records, and pipeline health statistics."""
        timeline = [{"moment_id": m.moment_id, "minute": m.minute_label, "kind": m.kind.value,
                     "importance": round(m.importance, RATE_DECIMALS),
                     "status": self.records[m.moment_id].status.value if m.moment_id in self.records else "not_aired"}
                    for m in moments]
        return {"hold": self.hold, "segments": segments, "timeline": timeline,
                "records": [r.to_dict() for r in reversed(self.records.values())], "health": pipeline_health(self.records)}


def pipeline_health(records: dict[str, BroadcastRecord]) -> dict[str, object]:
    """Per-role source rates, mean card latency, and fact-check verdict counts across all cues."""
    sources: dict[str, Counter[str]] = {role: Counter() for role in CUE_ROLES}
    verdicts: Counter[str] = Counter()
    latencies: list[int] = []
    cues = [cue for record in records.values() for cue in record.cues]
    for cue in cues:
        provenance = cue.get("provenance", {})
        assert isinstance(provenance, dict)
        for role in CUE_ROLES:
            entry = provenance.get(role)
            if isinstance(entry, dict):
                sources[role][str(entry["source"])] += 1
                if role == "card":
                    latencies.append(int(entry["latency_ms"]))
        check = provenance.get("fact_check")
        if isinstance(check, dict):
            verdicts[str(check["verdict"])] += 1
    rates = {role: {source: round(n / sum(c.values()), RATE_DECIMALS) for source, n in c.items()}
             for role, c in sources.items() if c}
    return {"moments": len(records), "cues": len(cues), "source_rates": rates, "fact_checks": dict(verdicts),
            "mean_card_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0}
