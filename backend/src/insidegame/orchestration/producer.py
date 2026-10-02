"""Producer policy deciding which key moments go to air and for which viewers.

It keeps the broadcast readable by enforcing a minimum gap between non-goal overlays and a per-event cap.
Goals always go to air; relevance per viewer is delegated to the persona rules.
"""

from dataclasses import dataclass

from insidegame.agents.context import ViewerContext
from insidegame.agents.personas import is_relevant
from insidegame.analytics.moments import KeyMoment, MomentKind

MIN_GAP_S: float = 45.0
MAX_MOMENTS_PER_EVENT: int = 2
PRIORITY_KINDS: frozenset[MomentKind] = frozenset({MomentKind.GOAL})


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
            if not audience or not self._gap_ok(moment) or len(chosen) >= MAX_MOMENTS_PER_EVENT:
                continue
            chosen.append((moment, audience))
            self.last_aired = (moment.period, moment.match_second)
        return chosen
