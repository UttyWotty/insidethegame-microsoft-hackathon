"""Pure rules and facts for expected threat (xT) key moments and for xT facts on existing pass moments.

A threat_created moment needs a completed pass that breaks a line and adds at least THREAT_MOMENT_MIN_XT, and it
cools down for THREAT_MOMENT_COOLDOWN_S match seconds within a period, whichever team played the pass.
Facts are JSON scalars rounded like the rest of the threat output, so agents can cite them and grounding accepts them.
"""

from dataclasses import dataclass

from insidegame.analytics.moments import FactValue
from insidegame.analytics.threat import XT_DECIMALS, ThreatAction
from insidegame.domain.enums import EventType

THREAT_MOMENT_MIN_XT: float = 0.025
THREAT_MOMENT_COOLDOWN_S: float = 300.0
THREAT_IMPORTANCE: float = 0.50
LINES_JOINER: str = " and "


@dataclass
class ThreatMomentRule:
    """Decides which threat actions raise a threat_created moment.

    Defaults: last is None until the first moment fires, then holds its (period, match second).
    """

    last: tuple[int, float] | None = None

    def _cooled_down(self, period: int, match_second: float) -> bool:
        return self.last is None or self.last[0] != period or match_second - self.last[1] >= THREAT_MOMENT_COOLDOWN_S

    def qualifies(self, threat: ThreatAction, period: int, match_second: float) -> bool:
        """True for a line-breaking pass adding enough xT outside the cooldown; records the time when True."""
        if (threat.action is not EventType.PASS or not threat.breaks_line or threat.xt_added < THREAT_MOMENT_MIN_XT
                or not self._cooled_down(period, match_second)):
            return False
        self.last = (period, match_second)
        return True


def lines_label(threat: ThreatAction) -> str:
    """Readable broken lines, for example "midfield and defence"; empty when no line was broken."""
    lines = threat.line_break.lines_broken if threat.line_break else ()
    return LINES_JOINER.join(line.value for line in lines)


def threat_facts(threat: ThreatAction, passer: str, receiver: str, length_m: float | None) -> dict[str, FactValue]:
    """Facts of a threat_created moment."""
    return {
        "passer": passer, "receiver": receiver, "xt_added": round(threat.xt_added, XT_DECIMALS),
        "xt_start": round(threat.xt_start, XT_DECIMALS), "xt_end": round(threat.xt_end, XT_DECIMALS),
        "opponents_bypassed": threat.line_break.opponents_bypassed if threat.line_break else None,
        "lines_broken": lines_label(threat), "length_m": length_m,
    }


def pass_threat_facts(threat: ThreatAction | None) -> dict[str, FactValue]:
    """xT facts added to difficult-pass and long-pass moments: xt_added, plus opponents_bypassed when known."""
    if threat is None:
        return {}
    facts: dict[str, FactValue] = {"xt_added": round(threat.xt_added, XT_DECIMALS)}
    if threat.line_break is not None:
        facts["opponents_bypassed"] = threat.line_break.opponents_bypassed
    return facts
