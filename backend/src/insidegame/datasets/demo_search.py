"""Command-line search for a demo seed: simulate the demo fixture per seed and rank the stories that pass every rule.

A cheap events-only pass skips seeds without a flagged go-ahead home goal, and survivors are re-analysed with
tracking positions, as the live service does, so shape shifts exist. Each survivor is scored by
insidegame.datasets.demo_story and printed in a deterministic Markdown table, best score first.
Usage: python -m insidegame.datasets.demo_search --start-seed 1 --end-seed 4000 --top 10
"""

import argparse
from dataclasses import astuple, fields

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.datasets.demo_story import GO_AHEAD, DemoStory, StoryCriteria, score_story
from insidegame.domain.match import MatchResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, TrackingModel

DEFAULT_START_SEED: int = 1
DEFAULT_END_SEED: int = 4000
DEFAULT_TOP: int = 10
DEFAULT_CRITERIA: StoryCriteria = StoryCriteria()


def _has_flagged_home_go_ahead(result: MatchResult) -> bool:
    """Cheap pre-filter on events-only analysis: a home goal that puts home ahead and links to a Scout flag."""
    analyzer = MatchAnalyzer(result.metadata)
    for event in result.events:
        analyzer.ingest(event)
    return any(m.kind is MomentKind.GOAL and "flagged_moment_id" in m.facts and m.facts["game_state_change"] == GO_AHEAD
               and m.team_id == result.metadata.home.team_id for m in analyzer.moments)


def tracked_analyzer(result: MatchResult) -> MatchAnalyzer:
    """Analyse a simulated match with the positions tracked before every event, as the live service does."""
    analyzer, tracking = MatchAnalyzer(result.metadata), TrackingModel(result.metadata)
    for index, event in enumerate(result.events):
        analyzer.ingest(event, tracking.previous or None)
        tracking.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
    return analyzer


def story_for_seed(seed: int, criteria: StoryCriteria) -> DemoStory | None:
    """Simulate the demo fixture for one seed and score its story, or None when it fails a rule."""
    result = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, seed))
    if not _has_flagged_home_go_ahead(result):
        return None
    return score_story(seed, result.metadata, result.events, tracked_analyzer(result).moments, criteria)


def _cell(value: object) -> str:
    if isinstance(value, tuple):
        return " ".join(str(v) for v in value)
    return str(value).replace("|", "/")


def story_table(stories: list[DemoStory]) -> str:
    """Markdown table of stories sorted by score (descending) then seed (ascending)."""
    names = [f.name for f in fields(DemoStory)]
    ranked = sorted(stories, key=lambda s: (-s.score, s.seed))
    lines = ["| " + " | ".join(names) + " |", "|" + "---|" * len(names)]
    lines += ["| " + " | ".join(_cell(v) for v in astuple(s)) + " |" for s in ranked]
    return "\n".join(lines)


def main() -> None:
    """Parse arguments, search the seed range, and print the top stories as a Markdown table."""
    parser = argparse.ArgumentParser(description="Rank demo seeds by the story their match tells.")
    parser.add_argument("--start-seed", type=int, default=DEFAULT_START_SEED)
    parser.add_argument("--end-seed", type=int, default=DEFAULT_END_SEED, help="inclusive")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    args = parser.parse_args()
    stories = [s for seed in range(args.start_seed, args.end_seed + 1)
               if (s := story_for_seed(seed, DEFAULT_CRITERIA)) is not None]
    top = sorted(stories, key=lambda s: (-s.score, s.seed))[:args.top]
    print(f"{len(stories)} of {args.end_seed - args.start_seed + 1} seeds pass every rule.")
    print(story_table(top))


if __name__ == "__main__":
    main()
