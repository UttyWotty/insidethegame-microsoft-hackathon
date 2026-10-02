"""Broadcast clock conventions shared by every layer that shows a minute to people.

Match minutes start at 1, and time beyond the end of a period is shown as added time, such as 45+3 or 90+1.
Keeping the rule in one place stops recaps, prompts, and overlays from disagreeing about the minute.
"""

from insidegame.core.constants import PERIOD_MINUTES, SECONDS_PER_MINUTE


def minute_label(match_second: float, period: int) -> str:
    """Return the broadcast minute label, for example 23', 45+3', or 90+1'."""
    period_end = PERIOD_MINUTES * period
    minute = int(match_second // SECONDS_PER_MINUTE) + 1
    return f"{period_end}+{minute - period_end}'" if minute > period_end else f"{minute}'"
