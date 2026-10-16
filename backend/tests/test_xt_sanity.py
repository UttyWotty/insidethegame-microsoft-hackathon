"""Tests for the pure expected threat (xT) sanity checks used by the calibration report.

Hand-built grids and dataset rows give known outcomes, so every check is verified to hold and to fail as expected.
The committed grid is also checked against the same rules, and labels must never collide with the band labels.
"""

from insidegame.analytics.xt_grid import XT_GRID
from insidegame.datasets.calibration import BENCHMARKS
from insidegame.datasets.xt_sanity import SanityCheck, sanity_table, xt_sanity

MATCHES = [{"match_id": "m1"}, {"match_id": "m2"}]
COLUMNS, ROWS = 12, 8
GOOD_EVENTS = [{"xt_added": 0.01}] * 6 + [{"xt_added": -0.004}] * 2 + [{"xt_added": None}] * 5
BAD_EVENTS = [{"xt_added": -0.01}] * 6 + [{"xt_added": 0.002}] * 2


def _rising_grid() -> tuple[tuple[float, ...], ...]:
    """Value rises with the column and peaks in the central rows of the last column."""
    return tuple(tuple(0.001 * (c + 1) + (0.05 if c == COLUMNS - 1 and r in (3, 4) else 0.0) for r in range(ROWS))
                 for c in range(COLUMNS))


def _falling_grid() -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(0.001 * (COLUMNS - c) for _ in range(ROWS)) for c in range(COLUMNS))


def test_all_checks_hold_for_a_sensible_grid_and_dataset() -> None:
    checks = xt_sanity(MATCHES, GOOD_EVENTS, _rising_grid())
    assert len(checks) == 4 and all(c.holds for c in checks)
    assert checks[2].value == "0.013" and checks[3].value == "75.0"


def test_checks_fail_for_a_backward_grid_and_threat_losing_dataset() -> None:
    checks = xt_sanity(MATCHES, BAD_EVENTS, _falling_grid())
    assert not any(c.holds for c in checks)


def test_committed_grid_passes_the_grid_checks() -> None:
    checks = xt_sanity(MATCHES, GOOD_EVENTS, XT_GRID)
    assert checks[0].holds and checks[1].holds


def test_empty_dataset_does_not_divide_by_zero() -> None:
    checks = xt_sanity([], [], _rising_grid())
    assert not checks[2].holds and not checks[3].holds


def test_table_renders_one_row_per_check_with_yes_or_no() -> None:
    table = sanity_table([SanityCheck("A", "1", "x", True), SanityCheck("B", "2", "y", False)])
    assert table.splitlines() == ["| Check | Synthetic | Expectation | Holds |", "|---|---|---|---|",
                                  "| A | 1 | x | yes |", "| B | 2 | y | no |"]


def test_labels_never_start_with_a_band_label() -> None:
    labels = [c.label for c in xt_sanity(MATCHES, GOOD_EVENTS, XT_GRID)]
    assert not [label for label in labels for b in BENCHMARKS if label.startswith(b.label)]
