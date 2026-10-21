"""Rule-based detection of key moments from the interpreted event stream.

MomentDetector watches shots, goals, saves, passes, and rhythm readings and emits KeyMoment records, and its
PatternMiner raises tactical patterns and links later goals and big chances back to them; line-breaking passes that
add enough expected threat (xT) raise threat_created moments, and sustained back-line shifts raise shape_shift moments.
Every rule threshold is a named constant so moments are reproducible and explainable.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.analytics.moments import FactValue, KeyMoment, MomentKind
from insidegame.analytics.pass_quality import PassQuality
from insidegame.analytics.pattern_rules import TacticalPattern
from insidegame.analytics.patterns import FlagRecord, PatternMiner
from insidegame.analytics.rhythm import RhythmReading
from insidegame.analytics.shape_moments import SHAPE_SHIFT_IMPORTANCE, shape_facts
from insidegame.analytics.shape_tracker import ShapeShift
from insidegame.analytics.tactical_facts import tactical_evidence
from insidegame.analytics.threat import ThreatAction
from insidegame.analytics.threat_moments import THREAT_IMPORTANCE, ThreatMomentRule, pass_threat_facts, threat_facts
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.core.geometry import distance_to_goal
from insidegame.domain.enums import EventType, Outcome, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

MAX_IMPORTANCE: float = 1.0
GOAL_BASE_IMPORTANCE: float = 0.85
LATE_MINUTE: int = 80
LATE_BONUS: float = 0.10
DECISIVE_BONUS: float = 0.05
BIG_CHANCE_XG: float = 0.25
BIG_CHANCE_BASE: float = 0.50
BIG_CHANCE_XG_WEIGHT: float = 0.50
GREAT_SAVE_XG: float = 0.15
GREAT_SAVE_BASE: float = 0.45
GREAT_SAVE_XG_WEIGHT: float = 0.60
SHOT_SPEED_THRESHOLD_KMH: float = 115.0
SPEED_IMPORTANCE: float = 0.35
LONG_PASS_THRESHOLD_M: float = 40.0
LONG_PASS_IMPORTANCE: float = 0.40
CARRY_MILESTONES_M: tuple[float, ...] = (300.0, 400.0)
CARRY_MILESTONE_IMPORTANCE: float = 0.35
DIFFICULT_PASS_THRESHOLD: float = 80.0
DIFFICULT_PASS_BASE: float = 0.30
DIFFICULT_PASS_SCALE: float = 100.0
MOMENTUM_SWING_THRESHOLD: float = 0.5
MIN_THREAT_FOR_SWING: float = 0.2
MOMENTUM_IMPORTANCE: float = 0.55
CHAOS_THRESHOLD: float = 0.85
CHAOS_IMPORTANCE: float = 0.40
RHYTHM_COOLDOWN_S: float = 2700.0
RHYTHM_WARMUP_S: float = 300.0
PASS_MILESTONES: frozenset[int] = frozenset({75})
PASS_MILESTONE_IMPORTANCE: float = 0.30
GOAL_MILESTONES: dict[int, tuple[str, float]] = {2: ("brace", 0.70), 3: ("hat_trick", 0.90)}
FACT_DECIMALS: int = 2
SPEED_DECIMALS: int = 1
TACTICAL_IMPORTANCE: float = 0.62


class GameStateChange(StrEnum):
    """How a goal changed the scoreline."""

    OPENER = "opener"
    EQUALISER = "equaliser"
    GO_AHEAD = "go_ahead"
    EXTENDS_LEAD = "extends_lead"
    PULLS_ONE_BACK = "pulls_one_back"


def _game_state_change(scorer_diff_after: int, total_goals: int) -> GameStateChange:
    if total_goals == 1:
        return GameStateChange.OPENER
    if scorer_diff_after == 0:
        return GameStateChange.EQUALISER
    if scorer_diff_after == 1:
        return GameStateChange.GO_AHEAD
    return GameStateChange.EXTENDS_LEAD if scorer_diff_after > 1 else GameStateChange.PULLS_ONE_BACK


@dataclass
class _ShotContext:
    event: MatchEvent
    xg: float
    assist_id: str | None


@dataclass
class MomentDetector:
    """Stateful detector producing KeyMoment records as events arrive."""

    metadata: MatchMetadata
    names: dict[str, str] = field(default_factory=dict)
    last_pass: tuple[int, str, str] | None = None
    last_shot: _ShotContext | None = None
    goals_by_player: Counter[str] = field(default_factory=Counter)
    completed_by_player: Counter[str] = field(default_factory=Counter)
    carried_by_player: Counter[str] = field(default_factory=Counter)
    last_rhythm_moment_s: dict[MomentKind, float] = field(default_factory=dict)
    momentum_side: Side | None = None
    period_start_s: float = 0.0
    count: int = 0
    miner: PatternMiner = field(init=False)
    threat_rule: ThreatMomentRule = field(default_factory=ThreatMomentRule)

    def __post_init__(self) -> None:
        self.miner = PatternMiner(self.metadata)
        for team in (self.metadata.home, self.metadata.away):
            self.names.update({p.player_id: p.name for p in team.players})

    def detect(
        self, event: MatchEvent, xg: float | None, quality: PassQuality | None, reading: RhythmReading,
        threat: ThreatAction | None = None, shifts: Sequence[ShapeShift] = (),
    ) -> list[KeyMoment]:
        """Return the key moments triggered by this event, possibly none.

        threat (default None) is the xT credit of a completed pass or carry; it adds xT facts to pass moments and
        can raise a threat_created moment. shifts (default empty) are the shape shifts this event completed, each
        raising a shape_shift moment.
        """
        kind = event.event_type
        if kind is EventType.PERIOD_START:
            self.last_rhythm_moment_s.clear()
            self.momentum_side = None
            self.period_start_s = event.match_second
        pattern = self.miner.observe(event)
        moments: list[KeyMoment] = [self._on_pattern(event, pattern)] if pattern is not None else []
        if kind is EventType.PASS and quality is not None:
            moments += self._on_pass(event, quality, threat)
        elif kind is EventType.SHOT and xg is not None:
            moments += self._on_shot(event, xg)
        elif kind is EventType.GOAL:
            moments += self._on_goal(event)
        elif kind is EventType.SAVE:
            moments += self._on_save(event)
        elif kind is EventType.CARRY:
            moments += self._on_carry(event)
        if threat is not None:
            moments += self._on_threat(event, threat)
        moments += [self._on_shape(event, shift, reading) for shift in shifts]
        return moments + self._on_rhythm(event, reading)

    def _moment(
        self, kind: MomentKind, event: MatchEvent, team_id: str | None, importance: float,
        player_ids: tuple[str, ...], event_ids: tuple[str, ...], facts: dict[str, FactValue],
    ) -> KeyMoment:
        self.count += 1
        return KeyMoment(
            moment_id=f"{self.metadata.match_id}-m{self.count:04d}", kind=kind, period=event.period,
            match_second=event.match_second, importance=min(importance, MAX_IMPORTANCE),
            team_id=team_id,
            player_ids=player_ids, event_ids=event_ids, facts=facts,
        )

    def _on_pattern(self, event: MatchEvent, pattern: TacticalPattern) -> KeyMoment:
        evidence = tactical_evidence(pattern, self.metadata)
        moment = self._moment(MomentKind.TACTICAL_PATTERN, event, pattern.team_id, TACTICAL_IMPORTANCE,
                              evidence.player_ids, (event.event_id,), evidence.facts)
        self.miner.record_flag(FlagRecord(pattern, moment.moment_id, moment.period, moment.match_second,
                                          moment.minute_label, str(evidence.facts["summary"])))
        return moment

    def _on_shape(self, event: MatchEvent, shift: ShapeShift, reading: RhythmReading) -> KeyMoment:
        return self._moment(MomentKind.SHAPE_SHIFT, event, shift.team_id, SHAPE_SHIFT_IMPORTANCE, (),
                            (event.event_id,), shape_facts(shift, self.metadata, reading))

    def _payoff_facts(self, event: MatchEvent) -> dict[str, FactValue]:
        link = self.miner.payoff(event)
        return link.facts() if link is not None else {}

    def _on_threat(self, event: MatchEvent, threat: ThreatAction) -> list[KeyMoment]:
        if threat.receiver_id is None or not self.threat_rule.qualifies(threat, event.period, event.match_second):
            return []
        length = round(event.length_m, FACT_DECIMALS) if event.length_m is not None else None
        facts = threat_facts(threat, self.names[threat.player_id], self.names[threat.receiver_id], length)
        return [self._moment(MomentKind.THREAT_CREATED, event, threat.team_id, THREAT_IMPORTANCE,
                             (threat.player_id, threat.receiver_id), (event.event_id,), facts)]

    def _on_pass(self, event: MatchEvent, quality: PassQuality, threat: ThreatAction | None) -> list[KeyMoment]:
        if event.outcome is not Outcome.SUCCESS or event.player_id is None or event.receiver_id is None:
            return []
        self.last_pass = (event.possession_id, event.player_id, event.receiver_id)
        self.completed_by_player[event.player_id] += 1
        moments: list[KeyMoment] = []
        completed = self.completed_by_player[event.player_id]
        if completed in PASS_MILESTONES:
            moments.append(self._moment(MomentKind.MILESTONE, event, event.team_id, PASS_MILESTONE_IMPORTANCE, (event.player_id,),
                                        (event.event_id,), {"milestone": f"{completed}_completed_passes",
                                                            "player": self.names[event.player_id]}))
        if quality.length_m >= LONG_PASS_THRESHOLD_M:
            moments.append(self._moment(MomentKind.DISTANCE_THRESHOLD, event, event.team_id, LONG_PASS_IMPORTANCE,
                                        (event.player_id, event.receiver_id), (event.event_id,), {
                                            "indicator": "long_pass", "passer": self.names[event.player_id],
                                            "receiver": self.names[event.receiver_id], "length_m": quality.length_m,
                                            "ball_speed_kmh": round(event.ball_speed_kmh or 0.0, SPEED_DECIMALS),
                                            "threshold_m": LONG_PASS_THRESHOLD_M, **pass_threat_facts(threat)}))
        if quality.difficulty >= DIFFICULT_PASS_THRESHOLD:
            importance = DIFFICULT_PASS_BASE + (quality.difficulty - DIFFICULT_PASS_THRESHOLD) / DIFFICULT_PASS_SCALE
            moments.append(self._moment(MomentKind.DIFFICULT_PASS, event, event.team_id, importance,
                                        (event.player_id, event.receiver_id), (event.event_id,), {
                                            "passer": self.names[event.player_id],
                                            "receiver": self.names[event.receiver_id],
                                            "difficulty": quality.difficulty, "length_m": quality.length_m,
                                            "under_pressure": event.under_pressure,
                                            "progressive": quality.progressive, **pass_threat_facts(threat)}))
        return moments

    def _on_shot(self, event: MatchEvent, xg: float) -> list[KeyMoment]:
        assist = None
        if self.last_pass and self.last_pass[0] == event.possession_id and self.last_pass[2] == event.player_id:
            assist = self.last_pass[1]
        self.last_shot = _ShotContext(event, xg, assist)
        if event.player_id is None or event.start is None:
            return []
        moments: list[KeyMoment] = []
        speed = event.ball_speed_kmh or 0.0
        if speed >= SHOT_SPEED_THRESHOLD_KMH:
            moments.append(self._moment(MomentKind.SPEED_THRESHOLD, event, event.team_id, SPEED_IMPORTANCE, (event.player_id,),
                                        (event.event_id,), {"player": self.names[event.player_id],
                                                            "shot_speed_kmh": round(speed, SPEED_DECIMALS),
                                                            "threshold_kmh": SHOT_SPEED_THRESHOLD_KMH}))
        if xg >= BIG_CHANCE_XG and event.outcome is not Outcome.SUCCESS:
            moments.append(self._moment(MomentKind.BIG_CHANCE_MISSED, event, event.team_id,
                                        BIG_CHANCE_BASE + BIG_CHANCE_XG_WEIGHT * xg, (event.player_id,),
                                        (event.event_id,), {"player": self.names[event.player_id], "xg": xg,
                                                            "result": event.shot_result.value if event.shot_result else None,
                                                            "distance_m": round(distance_to_goal(event.start), FACT_DECIMALS),
                                                            **self._payoff_facts(event)}))
        return moments

    def _on_goal(self, event: MatchEvent) -> list[KeyMoment]:
        if event.player_id is None or event.team_id is None or self.last_shot is None:
            return []
        shot = self.last_shot
        side = self.metadata.side_of(event.team_id)
        diff = event.score_home - event.score_away
        change = _game_state_change(diff if side is Side.HOME else -diff, event.score_home + event.score_away)
        minute = int(event.match_second // SECONDS_PER_MINUTE) + 1
        importance = GOAL_BASE_IMPORTANCE + (LATE_BONUS if minute >= LATE_MINUTE else 0.0)
        importance += DECISIVE_BONUS if change in (GameStateChange.EQUALISER, GameStateChange.GO_AHEAD) else 0.0
        self.goals_by_player[event.player_id] += 1
        players = (event.player_id,) + ((shot.assist_id,) if shot.assist_id else ())
        facts: dict[str, FactValue] = {
            "scorer": self.names[event.player_id],
            "assist": self.names[shot.assist_id] if shot.assist_id else None,
            "xg": shot.xg, "shot_speed_kmh": round(shot.event.ball_speed_kmh or 0.0, SPEED_DECIMALS),
            "distance_m": round(distance_to_goal(shot.event.start), FACT_DECIMALS) if shot.event.start else None,
            "game_state_change": change.value, "score_home": event.score_home, "score_away": event.score_away,
            **self._payoff_facts(event),
        }
        moments = [self._moment(MomentKind.GOAL, event, event.team_id, importance, players, (shot.event.event_id, event.event_id), facts)]
        milestone = GOAL_MILESTONES.get(self.goals_by_player[event.player_id])
        if milestone:
            moments.append(self._moment(MomentKind.MILESTONE, event, event.team_id, milestone[1], (event.player_id,),
                                        (event.event_id,), {"milestone": milestone[0],
                                                            "player": self.names[event.player_id]}))
        return moments

    def _on_carry(self, event: MatchEvent) -> list[KeyMoment]:
        if event.player_id is None or event.length_m is None:
            return []
        before = self.carried_by_player[event.player_id]
        after = before + event.length_m
        self.carried_by_player[event.player_id] = after
        crossed = [m for m in CARRY_MILESTONES_M if before < m <= after]
        return [self._moment(MomentKind.DISTANCE_THRESHOLD, event, event.team_id, CARRY_MILESTONE_IMPORTANCE,
                             (event.player_id,), (event.event_id,), {
                                 "indicator": "carry_distance", "player": self.names[event.player_id],
                                 "carry_distance_m": round(after, FACT_DECIMALS), "threshold_m": milestone})
                for milestone in crossed]

    def _on_save(self, event: MatchEvent) -> list[KeyMoment]:
        shot = self.last_shot
        if shot is None or event.player_id is None or shot.xg < GREAT_SAVE_XG or shot.event.player_id is None:
            return []
        return [self._moment(MomentKind.GREAT_SAVE, event, event.team_id, GREAT_SAVE_BASE + GREAT_SAVE_XG_WEIGHT * shot.xg,
                             (event.player_id, shot.event.player_id), (shot.event.event_id, event.event_id),
                             {"goalkeeper": self.names[event.player_id], "shooter": self.names[shot.event.player_id],
                              "xg_prevented": shot.xg,
                              "shot_speed_kmh": round(shot.event.ball_speed_kmh or 0.0, SPEED_DECIMALS)})]

    def _cooled_down(self, kind: MomentKind, now: float) -> bool:
        last = self.last_rhythm_moment_s.get(kind)
        return last is None or now - last >= RHYTHM_COOLDOWN_S

    def _on_rhythm(self, event: MatchEvent, reading: RhythmReading) -> list[KeyMoment]:
        moments: list[KeyMoment] = []
        now = event.match_second
        if now - self.period_start_s < RHYTHM_WARMUP_S:
            return moments
        if reading.home_threat + reading.away_threat >= MIN_THREAT_FOR_SWING:
            leader = (Side.HOME if reading.momentum >= MOMENTUM_SWING_THRESHOLD
                      else Side.AWAY if reading.momentum <= -MOMENTUM_SWING_THRESHOLD else None)
            if leader is not None and leader is not self.momentum_side:
                if self.momentum_side is not None and self._cooled_down(MomentKind.MOMENTUM_SWING, now):
                    self.last_rhythm_moment_s[MomentKind.MOMENTUM_SWING] = now
                    moments.append(self._moment(MomentKind.MOMENTUM_SWING, event, self.metadata.team(leader).team_id, MOMENTUM_IMPORTANCE, (), (), {
                        "to_side": leader.value, "momentum": round(reading.momentum, FACT_DECIMALS),
                        "home_threat": round(reading.home_threat, FACT_DECIMALS),
                        "away_threat": round(reading.away_threat, FACT_DECIMALS)}))
                self.momentum_side = leader
        if reading.chaos >= CHAOS_THRESHOLD and self._cooled_down(MomentKind.CHAOS_SPELL, now):
            self.last_rhythm_moment_s[MomentKind.CHAOS_SPELL] = now
            moments.append(self._moment(MomentKind.CHAOS_SPELL, event, None, CHAOS_IMPORTANCE, (), (), {
                "turnovers_per_minute": round(reading.turnovers_per_minute, FACT_DECIMALS),
                "chaos": round(reading.chaos, FACT_DECIMALS)}))
        return moments
