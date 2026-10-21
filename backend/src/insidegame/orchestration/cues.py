"""Overlay cues: the timed, machine-readable render contract for broadcast graphics (stage four).

A cue says what to show, for whom, in which layout, from which match second, and for how long.
Cues carry provenance so producers can see whether text came from a model, a retry, or a fallback, and why.
"""

from dataclasses import dataclass, field
from typing import Any

from insidegame.agents.personas import OverlayStyle
from insidegame.agents.runner import AgentOutcome, OutputSource
from insidegame.agents.context import MomentContext
from insidegame.agents.schemas import Commentary, Explanation
from insidegame.analytics.moments import KeyMoment, moment_intensity
from insidegame.domain.enums import Intensity
from insidegame.orchestration.messages import SKIPPED_CHECK, FactCheckRecord, PersonalizedCard

CUE_DELAY_S: float = 2.0
CUE_DURATION_S: dict[OverlayStyle, float] = {
    OverlayStyle.STAT_PANEL: 10.0,
    OverlayStyle.LOWER_THIRD: 6.0,
    OverlayStyle.HYPE_BANNER: 6.0,
    OverlayStyle.PLAYER_TAG: 8.0,
    OverlayStyle.EXPLAINER_CARD: 12.0,
}
DEFAULT_LANGUAGE: str = "en"
TIME_DECIMALS: int = 2


@dataclass(frozen=True)
class OverlayCue:
    """One overlay for one viewer."""

    cue_id: str
    match_id: str
    moment_id: str
    viewer_id: str
    persona: str
    language: str
    layout: str
    period: int
    display_from_s: float
    duration_s: float
    priority: float
    title: str
    body: str
    stat_callouts: list[dict[str, str]] = field(default_factory=list)
    commentary: str = ""
    commentary_language: str = DEFAULT_LANGUAGE
    commentary_intensity: str = Intensity.NORMAL.value
    theme: str = ""
    provenance: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return dict(self.__dict__)


def _text(item: PersonalizedCard) -> tuple[str, str, list[dict[str, str]], str]:
    card = item.card.value
    callouts = [{"label": c.label, "value": c.value} for c in card.stat_callouts]
    if item.translation is None or item.translation.source is OutputSource.FALLBACK:
        return card.title, card.body, callouts, DEFAULT_LANGUAGE
    translated = item.translation.value
    for callout, label in zip(callouts, translated.stat_labels, strict=False):
        callout["label"] = label
    return translated.card_title, translated.body, callouts, item.viewer.viewer.language


def _outcome_provenance(outcome: AgentOutcome[Any]) -> dict[str, object]:
    """Source, attempts, and latency of one outcome, plus its problems only when there are any.

    Omitting an empty problems list keeps normal model and fallback cues byte-identical to earlier releases, while
    degraded or retried outputs tell the producer why (for example "workflow degraded" or "template failed").
    """
    entry: dict[str, object] = {"source": outcome.source.value, "attempts": outcome.attempts,
                                "latency_ms": outcome.latency_ms}
    if outcome.problems:
        entry["problems"] = list(outcome.problems)
    return entry


def build_cue(
    match_id: str, moment: KeyMoment, explanation: AgentOutcome[Explanation],
    commentary: AgentOutcome[Commentary], item: PersonalizedCard, commentary_text: str | None = None,
    commentary_check: FactCheckRecord = SKIPPED_CHECK,
) -> OverlayCue:
    """Assemble the overlay cue for one viewer; commentary_text overrides the line with its translation.

    Defaults: commentary_text is None (the narrator's English line) and commentary_check is SKIPPED_CHECK. The cue
    records the commentary's own language, which can differ from the card's when only one translation succeeded.
    """
    profile = item.viewer.viewer.profile
    title, body, callouts, language = _text(item)
    outcomes = {"explanation": explanation, "commentary": commentary, "card": item.card}
    if item.translation is not None:
        outcomes["translation"] = item.translation
    provenance: dict[str, object] = {name: _outcome_provenance(o) for name, o in outcomes.items()}
    provenance["fact_check"] = item.fact_check.to_dict()
    provenance["commentary_check"] = commentary_check.to_dict()
    return OverlayCue(
        cue_id=f"{moment.moment_id}-{item.viewer.viewer.viewer_id}", match_id=match_id, moment_id=moment.moment_id,
        viewer_id=item.viewer.viewer.viewer_id, persona=profile.key.value, language=language,
        layout=profile.overlay_style.value, period=moment.period, display_from_s=round(moment.match_second + CUE_DELAY_S, TIME_DECIMALS),
        duration_s=CUE_DURATION_S[profile.overlay_style], priority=moment.importance, title=title, body=body,
        stat_callouts=callouts, commentary=commentary_text or commentary.value.line,
        commentary_language=item.viewer.viewer.language if commentary_text else DEFAULT_LANGUAGE,
        commentary_intensity=moment_intensity(moment.kind).value,
        theme=explanation.value.theme.value,
        provenance=provenance,
    )


@dataclass(frozen=True)
class MomentBroadcast:
    """Workflow output: everything produced for one key moment.

    Defaults: degraded is False; it is True when the workflow failed and templates produced the output.
    """

    context: MomentContext
    explanation: AgentOutcome[Explanation]
    commentary: AgentOutcome[Commentary]
    cues: tuple[OverlayCue, ...]
    degraded: bool = False
