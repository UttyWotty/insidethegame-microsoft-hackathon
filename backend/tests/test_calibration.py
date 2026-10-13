"""Tests for dataset calibration against reference bands.

Hand-built rows give exact expected rates, so the arithmetic, band checks, and table rendering are verified
without simulating matches. A generated dataset's card must include the calibration section.
"""

from pathlib import Path

from insidegame.datasets.calibration import BENCHMARKS, calibrate, calibration_table
from insidegame.datasets.generate import generate

MATCHES = [
    {"home_goals": 2, "away_goals": 1, "home_xg": 1.5, "away_xg": 1.0},
    {"home_goals": 1, "away_goals": 1, "home_xg": 1.2, "away_xg": 0.8},
]
EVENTS = (
    [{"event_type": "shot", "shot_result": "goal", "outcome": "success"}] * 5
    + [{"event_type": "shot", "shot_result": "saved", "outcome": "fail"}] * 5
    + [{"event_type": "shot", "shot_result": "off_target", "outcome": "fail"}] * 30
    + [{"event_type": "pass", "shot_result": None, "outcome": "success"}] * 80
    + [{"event_type": "pass", "shot_result": None, "outcome": "fail"}] * 20
)


def test_rates_are_computed_exactly_from_rows() -> None:
    values = {row.benchmark.key: row.value for row in calibrate(MATCHES, EVENTS)}
    assert values["goals_per_match"] == 2.5 and values["xg_per_match"] == 2.25
    assert values["goals_minus_xg"] == 0.25 and values["shots_per_match"] == 20.0
    assert values["on_target_pct"] == 25.0 and values["conversion_pct"] == 12.5
    assert values["pass_accuracy_pct"] == 80.0
    assert (values["home_win_pct"], values["draw_pct"], values["away_win_pct"]) == (50.0, 50.0, 0.0)


def test_band_flags_and_table_cover_every_benchmark() -> None:
    rows = calibrate(MATCHES, EVENTS)
    flags = {row.benchmark.key: row.within for row in rows}
    assert flags["goals_per_match"] and not flags["shots_per_match"] and not flags["draw_pct"]
    table = calibration_table(rows)
    assert table.count("\n") == len(BENCHMARKS) + 1 and "| Goals per match | 2.5 | 2.5 to 3.1 | yes |" in table


def test_generated_card_reports_calibration(tmp_path: Path) -> None:
    generate(2, 1, tmp_path)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "## Calibration" in card and "| Pass accuracy (%) |" in card
