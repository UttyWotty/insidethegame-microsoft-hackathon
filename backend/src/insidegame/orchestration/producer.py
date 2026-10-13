"""Producer policy deciding which key moments go to air and for which viewers.

It keeps the broadcast readable by enforcing a minimum gap between non-goal overlays and a per-event cap.
Goals always go to air and do not start the gap, so a brace or hat-trick on the same event still airs.
It also decides when a queued moment has fallen too far behind the match clock to be worth producing.
"""

from dataclasses import dataclass

from insidegame.agents.context import ViewerContext
from insidegame.agents.personas import is_relevant
from insidegame.analytics.moments import KeyMoment, MomentKind

MIN_GAP_S: float = 45.0
MAX_MOMENTS_PER_EVENT: int = 2
PRIORITY_KINDS: frozenset[MomentKind] = frozenset({MomentKind.GOAL})
STALE_MOMENT_MATCH_S: float = 300.0


def is_stale(moment: KeyMoment, period: int, match_second: float) -> bool:
    """True when a non-goal moment is too far behind the match clock to be worth producing.

    It mirrors the frontend's STALE_CUE_MATCH_S rule: overlays from an earlier period or more than
    STALE_MOMENT_MATCH_S match seconds old are never shown, so their agent work would be wasted. Goals never go stale.
    """
    if moment.kind in PRIORITY_KINDS:
        return False
    return moment.period != period or match_second - moment.match_second > STALE_MOMENT_MATCH_S


@dataclass
class ProducerPolicy:
    """Stateful selection of moments to broadcast.

    Defaults: last_aired is None (nothing aired yet in the current period).
    """

    last_aired: tuple[int, float] | None = None

    def _gap_ok(self, moment: KeyMoment) -> bool:
        if moment.kind in PRIORITY_KINDS or self.last_aired is None:
            return True
        period, second = self.last_aired
        return moment.period != period or moment.match_second - second >= MIN_GAP_S

    def select(
        self, moments: tuple[KeyMoment, ...], viewers: tuple[ViewerContext, ...]
    ) -> list[tuple[KeyMoment, tuple[ViewerContext, ...]]]:
        """Return the moments to air from one event, each with its relevant viewers."""
        chosen: list[tuple[KeyMoment, tuple[ViewerContext, ...]]] = []
        for moment in sorted(moments, key=lambda m: m.importance, reverse=True):
            audience = tuple(v for v in viewers if is_relevant(moment, v.viewer))
            follows_goal = any(m.kind in PRIORITY_KINDS for m, _ in chosen)
            if not audience or not (follows_goal or self._gap_ok(moment)) or len(chosen) >= MAX_MOMENTS_PER_EVENT:
                continue
            chosen.append((moment, audience))
            if moment.kind not in PRIORITY_KINDS:
                self.last_aired = (moment.period, moment.match_second)
        return chosen
