"""Command-line dataset generator: simulate many matches across every fixture pairing and write the tables.

Usage: python -m insidegame.datasets.generate --matches 48 --start-seed 1 --out data/synthetic
The output directory receives five JSON Lines files (including sampled 22-player tracking) and a dataset card.
"""

import argparse
import itertools
import json
from collections.abc import Iterable
from pathlib import Path

from insidegame.datasets.calibration import calibrate
from insidegame.datasets.card import dataset_card
from insidegame.datasets.rows import Row, build_tables
from insidegame.datasets.tracking_rows import tracking_rows
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import CLUB_PRESETS, build_fixture

DEFAULT_MATCHES: int = 12
DEFAULT_START_SEED: int = 1
DEFAULT_OUTPUT: Path = Path("data/synthetic")


def _write_jsonl(path: Path, rows: Iterable[Row]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def generate(matches: int, start_seed: int, output: Path) -> dict[str, int]:
    """Simulate and analyse matches, cycling through all home and away pairings, then write the dataset."""
    pairings = list(itertools.permutations(CLUB_PRESETS, 2))
    results = [simulate_match(build_fixture(*pairings[i % len(pairings)], start_seed + i)) for i in range(matches)]
    tables = [build_tables(result) for result in results]
    output.mkdir(parents=True, exist_ok=True)
    counts = {
        "matches": _write_jsonl(output / "matches.jsonl", (t.match for t in tables)),
        "events": _write_jsonl(output / "events.jsonl", (row for t in tables for row in t.events)),
        "players": _write_jsonl(output / "players.jsonl", (row for t in tables for row in t.players)),
        "moments": _write_jsonl(output / "moments.jsonl", (row for t in tables for row in t.moments)),
        "tracking": _write_jsonl(output / "tracking.jsonl", (row for r in results for row in tracking_rows(r))),
    }
    match_rows = [t.match for t in tables]
    calibration = calibrate(match_rows, (row for t in tables for row in t.events))
    card = dataset_card(match_rows, counts, calibration)
    (output / "README.md").write_text(card, encoding="utf-8")
    return counts


def main() -> None:
    """Parse arguments and generate the dataset."""
    parser = argparse.ArgumentParser(description="Generate a synthetic football event dataset.")
    parser.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    parser.add_argument("--start-seed", type=int, default=DEFAULT_START_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(generate(args.matches, args.start_seed, args.out)))


if __name__ == "__main__":
    main()
