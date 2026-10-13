"""Pure calibration of a synthetic dataset against approximate top-flight football reference bands.

It computes headline rates (goals, shots, accuracy, conversion, xG agreement, results by venue) from dataset rows
and flags each against a reference band, so realism is measured rather than claimed. Bands are approximate
typical ranges for top European leagues, intended as sanity checks, not as exact statistics.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from insidegame.datasets.rows import Row

PERCENT: float = 100.0
VALUE_DECIMALS: int = 2
SHOT: str = "shot"
PASS: str = "pass"
SUCCESS: str = "success"
ON_TARGET_RESULTS: frozenset[str] = frozenset({"goal", "saved"})


@dataclass(frozen=True)
class Benchmark:
    """An approximate reference band for one metric."""

    key: str
    label: str
    low: float
    high: float
    note: str = ""


BENCHMARKS: tuple[Benchmark, ...] = (
    Benchmark("goals_per_match", "Goals per match", 2.5, 3.1),
    Benchmark("xg_per_match", "Expected goals per match", 2.4, 3.2),
    Benchmark("goals_minus_xg", "Goals minus xG per match", -0.3, 0.3, "xG model agrees with simulated finishing"),
    Benchmark("shots_per_match", "Shots per match", 22.0, 28.0),
    Benchmark("on_target_pct", "Shots on target (%)", 30.0, 40.0, "blocked shots count as not on target"),
    Benchmark("conversion_pct", "Shot conversion (%)", 9.0, 13.0),
    Benchmark("pass_accuracy_pct", "Pass accuracy (%)", 78.0, 86.0),
    Benchmark("home_win_pct", "Home wins (%)", 40.0, 48.0, "needs a few hundred matches to settle"),
    Benchmark("draw_pct", "Draws (%)", 22.0, 30.0, "needs a few hundred matches to settle"),
    Benchmark("away_win_pct", "Away wins (%)", 25.0, 33.0, "needs a few hundred matches to settle"),
)


@dataclass(frozen=True)
class CalibrationRow:
    """One measured metric with its reference band."""

    benchmark: Benchmark
    value: float

    @property
    def within(self) -> bool:
        """Whether the measured value lies inside the reference band."""
        return self.benchmark.low <= self.value <= self.benchmark.high


def _share(part: float, whole: float) -> float:
    return PERCENT * part / whole if whole else 0.0


def _metrics(matches: Sequence[Row], events: Iterable[Row]) -> dict[str, float]:
    shots = on_target = passes = completed = 0
    for event in events:
        if event["event_type"] == SHOT:
            shots += 1
            on_target += event["shot_result"] in ON_TARGET_RESULTS
        elif event["event_type"] == PASS:
            passes += 1
            completed += event["outcome"] == SUCCESS
    n = len(matches) or 1
    home = [int(m["home_goals"]) for m in matches]  # type: ignore[call-overload]
    away = [int(m["away_goals"]) for m in matches]  # type: ignore[call-overload]
    goals = sum(home) + sum(away)
    xg = sum(float(m["home_xg"]) + float(m["away_xg"]) for m in matches)  # type: ignore[arg-type]
    return {
        "goals_per_match": goals / n, "xg_per_match": xg / n, "goals_minus_xg": (goals - xg) / n,
        "shots_per_match": shots / n, "on_target_pct": _share(on_target, shots),
        "conversion_pct": _share(goals, shots), "pass_accuracy_pct": _share(completed, passes),
        "home_win_pct": _share(sum(h > a for h, a in zip(home, away)), n),
        "draw_pct": _share(sum(h == a for h, a in zip(home, away)), n),
        "away_win_pct": _share(sum(h < a for h, a in zip(home, away)), n),
    }


def calibrate(matches: Sequence[Row], events: Iterable[Row]) -> list[CalibrationRow]:
    """Measure every benchmark metric over the dataset's match and event rows."""
    values = _metrics(matches, events)
    return [CalibrationRow(b, round(values[b.key], VALUE_DECIMALS)) for b in BENCHMARKS]


def calibration_table(rows: Sequence[CalibrationRow]) -> str:
    """Markdown table of measured values against their reference bands."""
    lines = ["| Metric | Synthetic | Reference band | Within band | Note |", "|---|---|---|---|---|"]
    for row in rows:
        b = row.benchmark
        lines.append(f"| {b.label} | {row.value} | {b.low} to {b.high} | {'yes' if row.within else 'no'} | {b.note} |")
    return "\n".join(lines)
