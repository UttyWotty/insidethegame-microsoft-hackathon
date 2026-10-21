"""Tests for the pure team-shape metrics: line height, length, width, compactness, and the block label.

They build home and away positions maps by hand (the away side mirrored into the absolute home frame) and compare
every metric with hand-computed values, check the block thresholds at their edges, and check missing players.
They also check that the shape modules import nothing from higher layers or from tracking and simulation.
"""

import math
import re
from pathlib import Path

import pytest
from shape_helpers import AWAY_LINE_M, FORWARD_GAP_M, LANE_YS, fixture, positions_for

from insidegame.analytics.shape import (
    HIGH_BLOCK_MIN_M,
    LOW_BLOCK_MAX_M,
    Block,
    ShapeMetrics,
    block_for,
    team_shape,
)
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import Position

ANALYTICS = Path(__file__).resolve().parents[1] / "src" / "insidegame" / "analytics"
SHAPE_MODULES = ("shape.py", "shape_tracker.py", "shape_moments.py")
FORBIDDEN_IMPORT = re.compile(r"^\s*(from|import) insidegame\.(tracking|simulation|agents|orchestration|api|live)\b",
                              re.MULTILINE)
JUST_BELOW_M = 0.001
HOME_LINE_M = 28.0


def _expected(line_m: float) -> tuple[float, float, float, float]:
    """Hand-computed metrics for the helper shape: 4 defenders, 3 midfielders, 3 forwards on LANE_YS."""
    xs = [line_m] * 4 + [line_m + 15.0] * 3 + [line_m + 30.0] * 3
    ys = list(LANE_YS) + list(LANE_YS[:3]) * 2
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    compactness = sum(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys, strict=True)) / len(xs)
    return line_m, FORWARD_GAP_M, max(ys) - min(ys), compactness


def test_home_shape_matches_hand_computed_values() -> None:
    metadata = fixture()
    metrics = team_shape(metadata.home, positions_for(metadata, HOME_LINE_M), is_home=True)
    assert metrics is not None
    line, length, width, compactness = _expected(HOME_LINE_M)
    assert metrics.line_height_m == pytest.approx(line) and metrics.length_m == pytest.approx(length)
    assert metrics.width_m == pytest.approx(width) and metrics.compactness_m == pytest.approx(compactness)


def test_away_shape_is_measured_in_its_own_mirrored_frame() -> None:
    metadata = fixture()
    positions = positions_for(metadata, HOME_LINE_M)
    defender = metadata.away.players_in(Position.DEFENDER)[0]
    assert positions[defender.player_id] == mirror(Point(AWAY_LINE_M, LANE_YS[0]))
    metrics = team_shape(metadata.away, positions, is_home=False)
    assert metrics is not None
    line, length, width, compactness = _expected(AWAY_LINE_M)
    assert metrics.line_height_m == pytest.approx(line) and metrics.length_m == pytest.approx(length)
    assert metrics.width_m == pytest.approx(width) and metrics.compactness_m == pytest.approx(compactness)


def test_block_thresholds_at_their_edges() -> None:
    assert block_for(HIGH_BLOCK_MIN_M) is Block.HIGH
    assert block_for(HIGH_BLOCK_MIN_M - JUST_BELOW_M) is Block.MID
    assert block_for(LOW_BLOCK_MAX_M) is Block.MID
    assert block_for(LOW_BLOCK_MAX_M - JUST_BELOW_M) is Block.LOW
    assert block_for((HIGH_BLOCK_MIN_M + LOW_BLOCK_MAX_M) / 2) is Block.MID
    assert ShapeMetrics(HIGH_BLOCK_MIN_M, 1.0, 1.0, 1.0).block is Block.HIGH


def test_missing_defender_or_too_few_outfield_players_gives_none() -> None:
    metadata = fixture()
    positions = positions_for(metadata, HOME_LINE_M)
    defender = metadata.home.players_in(Position.DEFENDER)[2].player_id
    assert team_shape(metadata.home, {k: v for k, v in positions.items() if k != defender}, is_home=True) is None
    assert team_shape(metadata.home, {}, is_home=True) is None


def test_to_dict_rounds_to_one_decimal_and_names_the_block() -> None:
    data = ShapeMetrics(23.456, 40.04, 47.99, 15.56).to_dict()
    assert data == {"line_height_m": 23.5, "length_m": 40.0, "width_m": 48.0, "compactness_m": 15.6, "block": "low"}


def test_shape_modules_import_nothing_from_higher_layers_tracking_or_simulation() -> None:
    for name in SHAPE_MODULES:
        source = (ANALYTICS / name).read_text(encoding="utf-8")
        assert not FORBIDDEN_IMPORT.search(source), name
