"""Plain-language explanations of football concepts for the newcomer persona.

Entries are keyed by the concept a moment illustrates, so a card can teach one idea at a time.
The same text is used by prompts as guidance and by fallback templates verbatim.
"""

from insidegame.analytics.moments import MomentKind

CONCEPTS: dict[MomentKind, tuple[str, str]] = {
    MomentKind.GOAL: ("Expected goals (xG)",
                      "xG is the chance a shot becomes a goal, from 0 to 1, based on where it was taken."),
    MomentKind.BIG_CHANCE_MISSED: ("Big chance",
                                   "A big chance is a shot that usually goes in, so missing it can change a match."),
    MomentKind.GREAT_SAVE: ("Goalkeeping",
                            "A great save stops a shot that had a good chance of becoming a goal."),
    MomentKind.SPEED_THRESHOLD: ("Shot speed",
                                 "Faster shots give the goalkeeper less time to react."),
    MomentKind.DISTANCE_THRESHOLD: ("Distance",
                                    "Long passes switch play quickly, and players who carry the ball far drive their team forward."),
    MomentKind.DIFFICULT_PASS: ("Pass difficulty",
                                "Long passes under pressure into the attacking third are the hardest to complete."),
    MomentKind.MOMENTUM_SWING: ("Momentum",
                                "Momentum is which team has been creating more danger over the last few minutes."),
    MomentKind.CHAOS_SPELL: ("Turnovers",
                             "A turnover is when a team loses the ball; many in a row make a match chaotic."),
    MomentKind.MILESTONE: ("Milestones",
                           "A brace is two goals by one player, and a hat-trick is three."),
}


def concept_for(kind: MomentKind) -> tuple[str, str]:
    """Return the (term, explanation) pair taught by a moment kind."""
    return CONCEPTS[kind]
