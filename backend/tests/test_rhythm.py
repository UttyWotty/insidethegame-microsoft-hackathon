"""Tests for the rolling momentum, control, and chaos model.

Synthetic hand-built events drive the tracker so each behaviour is isolated.
No simulator or I/O is involved.
"""

from insidegame.analytics.rhythm import RhythmState, RhythmTracker
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Outcome, Side
from insidegame.domain.events import MatchEvent


def _event(second: float, kind: EventType, team: str | None = "brk", outcome: Outcome | None = None) -> MatchEvent:
    return MatchEvent(
        event_id=f"e{second}", match_id="m", sequence=int(second), period=1, match_second=second,
        event_type=kind, team_id=team, player_id=None, possession_id=0, start=Point(50, 34),
        score_home=0, score_away=0, outcome=outcome,
    )


def test_shots_by_one_side_create_momentum() -> None:
    tracker = RhythmTracker()
    tracker.update(_event(0, EventType.PERIOD_START, None), None, None, None)
    reading = None
    for second in range(60, 300, 60):
        reading = tracker.update(_event(second, EventType.SHOT), Side.HOME, 0.2, None)
    assert reading is not None and reading.momentum > 0.9
    assert reading.state is RhythmState.HOME_PRESSURE


def test_frequent_turnovers_register_as_chaos() -> None:
    tracker = RhythmTracker()
    tracker.update(_event(0, EventType.PERIOD_START, None), None, None, None)
    reading = None
    for i in range(30):
        reading = tracker.update(_event(i * 10.0, EventType.POSSESSION_CHANGE), Side.HOME, None, None)
    assert reading is not None and reading.chaos == 1.0
    assert reading.state is RhythmState.CHAOS


def test_pass_dominance_registers_as_control() -> None:
    tracker = RhythmTracker()
    tracker.update(_event(0, EventType.PERIOD_START, None), None, None, None)
    reading = None
    for i in range(40):
        reading = tracker.update(_event(i * 5.0, EventType.PASS, outcome=Outcome.SUCCESS), Side.AWAY, None, None)
    assert reading is not None and reading.home_pass_share == 0.0
    assert reading.state is RhythmState.AWAY_CONTROL


def test_old_samples_leave_the_window() -> None:
    tracker = RhythmTracker()
    tracker.update(_event(0, EventType.PERIOD_START, None), None, None, None)
    tracker.update(_event(10, EventType.SHOT), Side.HOME, 0.5, None)
    reading = tracker.update(_event(1000, EventType.PASS, outcome=Outcome.SUCCESS), Side.AWAY, None, None)
    assert reading.home_threat == 0.0


def test_rhythm_moments_wait_for_warmup() -> None:
    from insidegame.analytics.detectors import RHYTHM_WARMUP_S, MomentDetector
    from insidegame.analytics.moments import MomentKind
    from insidegame.simulation.roster import build_fixture

    detector = MomentDetector(build_fixture("brookhaven", "ironvale", 1))
    tracker = RhythmTracker()
    early_moments = []
    detector.detect(_event(0, EventType.PERIOD_START, None), None, None, tracker.update(_event(0, EventType.PERIOD_START, None), None, None, None))
    for i in range(1, 30):
        reading = tracker.update(_event(i * 5.0, EventType.POSSESSION_CHANGE), Side.HOME, None, None)
        early_moments += detector.detect(_event(i * 5.0, EventType.POSSESSION_CHANGE), None, None, reading)
    assert i * 5.0 < RHYTHM_WARMUP_S
    assert not [m for m in early_moments if m.kind is MomentKind.CHAOS_SPELL]
