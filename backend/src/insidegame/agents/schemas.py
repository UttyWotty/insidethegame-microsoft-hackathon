"""Pydantic output schemas that every agent must return as structured JSON.

Structured outputs make agent results machine-readable for overlays and verifiable by the grounding check.
Field descriptions double as instructions to the model about what each field must contain.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

MAX_EVIDENCE_ITEMS: int = 4
MAX_STAT_CALLOUTS: int = 3
MAX_RECAP_MOMENTS: int = 6
MAX_FOLLOW_UPS: int = 3
MAX_FACT_ISSUES: int = 3


class TacticalTheme(StrEnum):
    """The underlying football reason a moment matters."""

    CONTROL = "control"
    CHAOS = "chaos"
    PRESSURE_SHIFT = "pressure_shift"
    INDIVIDUAL_BRILLIANCE = "individual_brilliance"
    CLINICAL_FINISHING = "clinical_finishing"
    MISSED_OPPORTUNITY = "missed_opportunity"
    GOALKEEPING = "goalkeeping"
    MILESTONE = "milestone"


class Explanation(BaseModel):
    """Analyst output: why a moment matters, grounded in evidence."""

    headline: str = Field(description="At most 12 words naming what happened.")
    why_it_matters: str = Field(description="Two sentences explaining the consequence for the match, not a replay of the event.")
    evidence: list[str] = Field(description="Short factual statements, each citing a number from the provided facts.",
                                max_length=MAX_EVIDENCE_ITEMS)
    theme: TacticalTheme = Field(description="The single best-fitting tactical theme.")


class Commentary(BaseModel):
    """Narrator output: one broadcast commentary line."""

    line: str = Field(description="One vivid sentence a commentator could say live, at most 30 words.")


class StatCallout(BaseModel):
    """A label and value pair rendered as an on-screen stat."""

    label: str = Field(description="Short label, at most 4 words.")
    value: str = Field(description="The value exactly as it appears in the facts, with unit if any.")


class PersonaCard(BaseModel):
    """Personalizer output: the on-screen card for one persona."""

    title: str = Field(description="At most 8 words.")
    body: str = Field(description="The persona's message, within its word budget.")
    stat_callouts: list[StatCallout] = Field(description="Up to 3 stats from the persona's focus list.",
                                             max_length=MAX_STAT_CALLOUTS)


class TranslatedCard(BaseModel):
    """Translator output: a persona card rendered in the viewer's language."""

    title: str
    body: str
    stat_labels: list[str] = Field(description="Translated stat labels in the same order as the input.")


class MatchRecap(BaseModel):
    """Recap output: an automated full-time or half-time summary."""

    headline: str = Field(description="At most 12 words.")
    summary: str = Field(description="Three to four sentences telling the story of the match.")
    turning_points: list[str] = Field(description="Key moments in match order, each with its minute.",
                                      max_length=MAX_RECAP_MOMENTS)
    standout_player: str = Field(description="Name of the most influential player, taken from the facts.")
    tactical_story: str = Field(description="One or two sentences on how control, chaos, or pressure shaped the result.")


class CompanionAnswer(BaseModel):
    """Match Companion output: a grounded answer to a viewer's question."""

    answer: str = Field(description="Direct answer in the persona's voice and the requested language, at most 80 words. "
                                    "If the question is not about this match, politely decline and suggest one that is.")
    stat_callouts: list[StatCallout] = Field(description="Up to 3 stats that support the answer.",
                                             max_length=MAX_STAT_CALLOUTS)
    follow_ups: list[str] = Field(description="Up to 3 short follow-up questions about this match.",
                                  max_length=MAX_FOLLOW_UPS)


class RecapTake(BaseModel):
    """Personalizer output: one persona's take on a half-time or full-time recap."""

    headline: str = Field(description="At most 10 words, in the persona's voice.")
    take: str = Field(description="The persona's view of the match so far, within its word budget.")


class TranslatedLine(BaseModel):
    """Translator output for a single commentary line."""

    line: str = Field(description="The commentary line in the target language, names and numbers unchanged.")


class FactCheckVerdict(BaseModel):
    """Fact-checker output: whether a draft is accurate, and what is wrong if not."""

    approved: bool = Field(description="True only if every claim in the draft is supported by the facts.")
    issues: list[str] = Field(description="Specific factual problems, each naming the wrong claim and the correct fact.",
                              max_length=MAX_FACT_ISSUES)
