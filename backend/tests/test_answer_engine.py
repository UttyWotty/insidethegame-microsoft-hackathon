"""Tests for the deterministic, persona-voiced answer engine used when no model answer is available.

They cover intent detection, grounding of every number, and how each persona changes the same answer.
Inputs come from a real simulated match.
"""

from insidegame.agents.answer_engine import Intent, detect_intent, rule_based_answer
from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.grounding import check_grounding
from insidegame.agents.personas import PersonaKey, ViewerProfile
from insidegame.agents.question_context import QuestionContext, build_question_context
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind

QUESTIONS = ("Who has been the best player so far?", "Which team is in control?", "Why has the momentum changed?",
             "What's the score?")


def _context(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> QuestionContext:
    return build_question_context(analysed_match[0])


def test_intents_are_detected(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    context = _context(analysed_match)
    assert [detect_intent(q, context)[0] for q in QUESTIONS] == [
        Intent.BEST_PLAYER, Intent.ON_TOP, Intent.MOMENTUM, Intent.SCORE]
    name = next(iter(context.players))
    assert detect_intent(f"How is {name} doing?", context) == (Intent.PLAYER, name)


def test_every_answer_is_grounded_in_live_statistics(
    analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]],
) -> None:
    context = _context(analysed_match)
    evidence = [context.to_prompt_dict(), context.players]
    viewer = ViewerContext(ViewerProfile("a", PersonaKey.ANALYST))
    for question in (*QUESTIONS, f"How is {next(iter(context.players))} doing?"):
        answer = rule_based_answer(question, context, viewer)
        texts = [answer.answer, *(c.value for c in answer.stat_callouts)]
        assert check_grounding(texts, evidence).grounded, (question, answer.answer)
        assert answer.follow_ups


def test_personas_change_the_same_answer(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> None:
    context = _context(analysed_match)
    home = analysed_match[0].metadata.home
    tracked = home.players[-2]
    viewers = {
        "analyst": ViewerContext(ViewerProfile("a", PersonaKey.ANALYST)),
        "casual": ViewerContext(ViewerProfile("c", PersonaKey.CASUAL)),
        "superfan": ViewerContext(ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id=home.team_id), home.name),
        "tracker": ViewerContext(ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id=tracked.player_id),
                                 tracked_player_name=tracked.name),
        "newcomer": ViewerContext(ViewerProfile("n", PersonaKey.NEWCOMER)),
    }
    answers = {k: rule_based_answer("Which team is in control?", context, v) for k, v in viewers.items()}
    assert len({a.answer for a in answers.values()}) == len(viewers)
    assert answers["superfan"].answer.startswith(("We're on top!", "They're edging it"))
    assert " we (" not in answers["superfan"].answer and " 1 shots" not in answers["analyst"].answer
    assert tracked.name in answers["tracker"].answer
    assert "expected goals" in answers["newcomer"].answer
    assert not answers["casual"].stat_callouts and len(answers["casual"].answer) < len(answers["analyst"].answer)
