"""Tests that the degraded broadcast survives every template failing for every moment kind and broadcast minute.

The fixture match does not produce every kind, so each MomentKind is forced onto a real context, including kinds such
as shape_shift, threat_created, milestone, and great_save, at regular and added-time minutes in both halves.
Every viewer, including non-English ones and a player tracker whose favourite player is not in the match, must get a
cue whose title, body, and commentary pass the validators and the numeric grounding check against the moment alone.
"""

from dataclasses import replace

import pytest

from insidegame.agents.context import MomentContext, ViewerContext, build_viewer_context
from insidegame.agents.grounding import check_grounding
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.schemas import PersonaCard, StatCallout
from insidegame.agents.validation import card_validator, commentary_validator, explanation_validator
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.orchestration import service
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.minimal_outputs import TEMPLATE_FAILED_NOTE
from insidegame.orchestration.service import degraded_broadcast

MATCH_ID = "m-kinds"
TEMPLATE_NAMES = ("explanation_template", "commentary_template", "persona_card_template")
GHOST_PLAYER_ID = "not-in-this-match"
HALF_SECONDS = 45 * 60
MINUTES: tuple[tuple[int, float], ...] = ((1, 0.0), (1, HALF_SECONDS + 330.0), (2, HALF_SECONDS + 1.0),
                                          (2, 2 * HALF_SECONDS + 600.0))


def _viewers(analyzer: MatchAnalyzer) -> tuple[ViewerContext, ...]:
    meta = analyzer.metadata
    profiles = [ViewerProfile("an", PersonaKey.ANALYST, "de"), ViewerProfile("ca", PersonaKey.CASUAL, "fr"),
                ViewerProfile("sf", PersonaKey.SUPERFAN, "es", favourite_team_id=meta.away.team_id),
                ViewerProfile("pt", PersonaKey.PLAYER_TRACKER, "ja", favourite_player_id=GHOST_PLAYER_ID),
                ViewerProfile("nc", PersonaKey.NEWCOMER)]
    return tuple(build_viewer_context(p, meta) for p in profiles)


def _fail(*args: object) -> object:
    raise RuntimeError("template boom")


@pytest.mark.parametrize("kind", list(MomentKind), ids=lambda k: k.value)
def test_every_kind_and_minute_survives_all_templates_failing(
        kind: MomentKind, goal_context: MomentContext,
        analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    for name in TEMPLATE_NAMES:
        monkeypatch.setattr(service, name, _fail)
    viewers = _viewers(analysed_match[0])
    for period, second in MINUTES:
        moment = replace(goal_context.moment, kind=kind, period=period, match_second=second)
        context = replace(goal_context, moment=moment)
        broadcast = degraded_broadcast(MATCH_ID, context, MomentJob(context, viewers))
        prompt = context.to_prompt_dict()
        evidence = [prompt, broadcast.explanation.value.model_dump(mode="json")]
        assert TEMPLATE_FAILED_NOTE in broadcast.explanation.problems
        assert TEMPLATE_FAILED_NOTE in broadcast.commentary.problems
        assert explanation_validator(lambda: [prompt])(broadcast.explanation.value) is None
        assert commentary_validator(lambda: evidence)(broadcast.commentary.value) is None
        assert [c.viewer_id for c in broadcast.cues] == [v.viewer.viewer_id for v in viewers]
        for cue, viewer in zip(broadcast.cues, viewers, strict=True):
            card = PersonaCard(title=cue.title, body=cue.body,
                               stat_callouts=[StatCallout(**c) for c in cue.stat_callouts])
            assert card_validator(lambda: evidence, viewer.viewer.profile.max_words)(card) is None
            assert check_grounding([cue.title, cue.body, cue.commentary], [prompt]).grounded
