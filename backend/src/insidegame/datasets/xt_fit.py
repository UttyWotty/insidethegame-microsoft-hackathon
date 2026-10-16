"""Command-line fit of the expected threat (xT) grid from simulated matches, written as a generated Python module.

Usage: python -m insidegame.datasets.xt_fit --matches 480 --start-seed 1 --out backend/src/insidegame/analytics/xt_grid.py
It simulates every home and away pairing, counts transitions, solves the grid by value iteration, and symmetrises it.
The output carries no date, so regenerating an unchanged simulator reproduces the committed module byte for byte.
"""

import argparse
import itertools
from pathlib import Path

from insidegame.analytics.xt_model import XtGrid, empty_counts, symmetrise, value_iteration
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import CLUB_PRESETS, build_fixture

DEFAULT_MATCHES: int = 480
DEFAULT_START_SEED: int = 1
DEFAULT_OUTPUT: Path = Path("backend/src/insidegame/analytics/xt_grid.py")
XT_GRID_DECIMALS: int = 4
MODULE_HEADER: str = '''"""Generated expected threat (xT) grid fitted to the Inside the Game synthetic league; do not edit by hand.

It was produced by insidegame.datasets.xt_fit from {matches} simulated matches (seeds {first} to {last}).
Regenerate it with that command whenever the simulator changes, because the values depend on simulated play.
"""

from insidegame.analytics.xt_model import XtGrid

XT_FIT_MATCHES: int = {matches}
XT_FIT_START_SEED: int = {first}
XT_GRID: XtGrid = (
'''


def fit_grid(matches: int, start_seed: int) -> XtGrid:
    """Simulate matches over every home and away pairing and return the symmetrised xT grid."""
    pairings = list(itertools.permutations(CLUB_PRESETS, 2))
    counts = empty_counts()
    for i in range(matches):
        for event in simulate_match(build_fixture(*pairings[i % len(pairings)], start_seed + i)).events:
            counts.add_event(event)
    return symmetrise(value_iteration(counts))


def render_grid_module(grid: XtGrid, matches: int, start_seed: int) -> str:
    """Return the source of the generated grid module, one column (own goal line first) per line."""
    header = MODULE_HEADER.format(matches=matches, first=start_seed, last=start_seed + matches - 1)
    body = "".join(
        "    (" + ", ".join(f"{value:.{XT_GRID_DECIMALS}f}" for value in column) + "),\n" for column in grid)
    return header + body + ")\n"


def main() -> None:
    """Parse arguments, fit the grid, and write the generated module."""
    parser = argparse.ArgumentParser(description="Fit the expected threat (xT) grid from simulated matches.")
    parser.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    parser.add_argument("--start-seed", type=int, default=DEFAULT_START_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.out.write_text(render_grid_module(fit_grid(args.matches, args.start_seed), args.matches, args.start_seed),
                        encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
