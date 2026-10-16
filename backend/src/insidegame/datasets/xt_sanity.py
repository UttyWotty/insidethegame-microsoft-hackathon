"""Pure sanity checks of the fitted expected threat (xT) grid and of the xT added in a synthetic dataset.

They check that the most valuable cell lies in the penalty area, that value rises third by third toward goal,
that teams add positive xT per match, and that most completed passes and carries move the ball somewhere more
dangerous. Each check renders as one row of a Markdown table in the calibration report.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from insidegame.analytics.xt_model import XtGrid
from insidegame.core.constants import GOAL_CENTER_Y_M, PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.datasets.calibration import BOX_DEPTH_M, BOX_HALF_WIDTH_M
from insidegame.datasets.rows import Row

XT_VALUE_DECIMALS: int = 3
SHARE_DECIMALS: int = 1
PERCENT: float = 100.0
HALF: float = 0.5
THIRDS: int = 3
TEAMS_PER_MATCH: int = 2
MIN_THREAT_SHARE_PCT: float = 50.0
THIRD_NAMES: tuple[str, ...] = ("defensive", "middle", "final")
PEAK_LABEL: str = "xT peak cell"
THIRDS_LABEL: str = "xT mean cell value by third (defensive, middle, final)"
PER_TEAM_LABEL: str = "xT added per team per match"
SHARE_LABEL: str = "Completed passes and carries adding xT (%)"


@dataclass(frozen=True)
class SanityCheck:
    """One xT sanity check: what was measured, what is expected, and whether it holds."""

    label: str
    value: str
    expectation: str
    holds: bool


def _cell_centre(column: int, row: int, columns: int, rows: int) -> tuple[float, float]:
    return (column + HALF) * PITCH_LENGTH_M / columns, (row + HALF) * PITCH_WIDTH_M / rows


def _peak_check(grid: XtGrid) -> SanityCheck:
    columns, rows = len(grid), len(grid[0])
    column, row = max(((c, r) for c in range(columns) for r in range(rows)), key=lambda cell: grid[cell[0]][cell[1]])
    x, y = _cell_centre(column, row, columns, rows)
    inside = PITCH_LENGTH_M - x <= BOX_DEPTH_M and abs(y - GOAL_CENTER_Y_M) <= BOX_HALF_WIDTH_M
    value = f"{grid[column][row]:.{XT_VALUE_DECIMALS}f} at {x:.1f} m, {y:.1f} m"
    return SanityCheck(PEAK_LABEL, value, "inside the attacked penalty area", inside)


def _thirds_check(grid: XtGrid) -> SanityCheck:
    columns = len(grid)
    sums, counts = [0.0] * THIRDS, [0] * THIRDS
    for column, values in enumerate(grid):
        third = column * THIRDS // columns
        sums[third] += sum(values)
        counts[third] += len(values)
    means = [s / n if n else 0.0 for s, n in zip(sums, counts)]
    rising = all(a < b for a, b in zip(means, means[1:]))
    value = ", ".join(f"{m:.{XT_VALUE_DECIMALS}f}" for m in means)
    return SanityCheck(THIRDS_LABEL, value, f"rises from {THIRD_NAMES[0]} to {THIRD_NAMES[-1]} third", rising)


def xt_sanity(matches: Sequence[Row], events: Iterable[Row], grid: XtGrid) -> list[SanityCheck]:
    """Run the four xT sanity checks on a grid and on the xT added in dataset event rows."""
    total, credited, positive = 0.0, 0, 0
    for event in events:
        added = event.get("xt_added")
        if added is None:
            continue
        total += float(added)  # type: ignore[arg-type]
        credited += 1
        positive += float(added) > 0  # type: ignore[arg-type]
    team_matches = TEAMS_PER_MATCH * len(matches)
    per_team = total / team_matches if team_matches else 0.0
    share = PERCENT * positive / credited if credited else 0.0
    return [
        _peak_check(grid), _thirds_check(grid),
        SanityCheck(PER_TEAM_LABEL, f"{per_team:.{XT_VALUE_DECIMALS}f}", "positive", per_team > 0),
        SanityCheck(SHARE_LABEL, f"{share:.{SHARE_DECIMALS}f}", f"above {MIN_THREAT_SHARE_PCT:g}",
                    share > MIN_THREAT_SHARE_PCT),
    ]


def sanity_table(checks: Sequence[SanityCheck]) -> str:
    """Markdown table of the xT sanity checks."""
    lines = ["| Check | Synthetic | Expectation | Holds |", "|---|---|---|---|"]
    lines += [f"| {c.label} | {c.value} | {c.expectation} | {'yes' if c.holds else 'no'} |" for c in checks]
    return "\n".join(lines)
