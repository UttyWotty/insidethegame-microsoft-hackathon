"""One resilient operation per agent role: explain, narrate, personalize, and translate.

Each step builds its prompt, evidence, validator, and fallback, then delegates to run_resilient.
Orchestration executors call these steps so workflow wiring stays separate from agent behaviour.
"""

from insidegame.agents.answer_engine import rule_based_answer
from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import AgentSuite
from insidegame.agents.prompts import (
    analyst_prompt,
    companion_prompt,
    line_translation_prompt,
    narrator_prompt,
    personalizer_prompt,
    recap_prompt,
    recap_take_prompt,
    translator_prompt,
)
from insidegame.agents.question_context import QuestionContext
from insidegame.agents.recap_context import RecapContext
from insidegame.agents.recap_takes import template_take
from insidegame.agents.runner import AgentOutcome, RunPolicy, run_resilient
from insidegame.agents.schemas import (
    Commentary,
    CompanionAnswer,
    Explanation,
    MatchRecap,
    PersonaCard,
    RecapTake,
    TranslatedCard,
    TranslatedLine,
)
from insidegame.agents.templates import (
    commentary_template,
    explanation_template,
    persona_card_template,
    recap_template,
    untranslated_card,
)
from insidegame.agents.tools import EvidenceLedger, build_analyst_tools
from insidegame.agents.validation import (
    answer_validator,
    card_validator,
    commentary_validator,
    explanation_validator,
    line_translation_validator,
    recap_validator,
    take_validator,
    translation_validator,
)
from insidegame.analytics.analyzer import MatchAnalyzer


async def explain(
    suite: AgentSuite, context: MomentContext, analyzer: MatchAnalyzer, policy: RunPolicy
) -> AgentOutcome[Explanation]:
    """Ask the analyst why the moment matters, allowing statistics tool calls."""
    ledger = EvidenceLedger()
    tools = build_analyst_tools(analyzer, ledger, as_of=context)
    validator = explanation_validator(lambda: [context.to_prompt_dict(), ledger.entries])
    return await run_resilient(suite.analyst, analyst_prompt(context), Explanation, validator,
                               lambda: explanation_template(context), policy, tools)


async def narrate(
    suite: AgentSuite, context: MomentContext, explanation: Explanation, policy: RunPolicy
) -> AgentOutcome[Commentary]:
    """Ask the narrator for a live commentary line."""
    validator = commentary_validator(lambda: [context.to_prompt_dict(), explanation.model_dump(mode="json")])
    return await run_resilient(suite.narrator, narrator_prompt(context, explanation), Commentary, validator,
                               lambda: commentary_template(context, explanation), policy)


async def personalize(
    suite: AgentSuite, context: MomentContext, explanation: Explanation, viewer: ViewerContext, policy: RunPolicy
) -> AgentOutcome[PersonaCard]:
    """Ask the personalizer for one persona's on-screen card."""
    validator = card_validator(lambda: [context.to_prompt_dict(), explanation.model_dump(mode="json")],
                               viewer.viewer.profile.max_words)
    return await run_resilient(suite.personalizer, personalizer_prompt(context, explanation, viewer), PersonaCard,
                               validator, lambda: persona_card_template(context, explanation, viewer), policy)


async def translate(
    suite: AgentSuite, card: PersonaCard, language: str, policy: RunPolicy
) -> AgentOutcome[TranslatedCard]:
    """Ask the translator to localise a card, keeping the English card as the fallback."""
    return await run_resilient(suite.translator, translator_prompt(card, language), TranslatedCard,
                               translation_validator(card), lambda: untranslated_card(card), policy)


async def write_recap(
    suite: AgentSuite, context: RecapContext, analyzer: MatchAnalyzer, policy: RunPolicy
) -> AgentOutcome[MatchRecap]:
    """Ask the editor for a recap, restricting the standout player to real squad members."""
    names = {p.name for p in analyzer.stats.players.values()}
    validator = recap_validator(context.to_prompt_dict(), names)
    return await run_resilient(suite.editor, recap_prompt(context), MatchRecap, validator,
                               lambda: recap_template(context), policy)


async def answer_question(
    suite: AgentSuite, question: str, context: QuestionContext, viewer: ViewerContext, analyzer: MatchAnalyzer,
    policy: RunPolicy,
) -> AgentOutcome[CompanionAnswer]:
    """Ask the Match Companion a viewer's question, allowing statistics tool calls."""
    ledger = EvidenceLedger()
    tools = build_analyst_tools(analyzer, ledger)
    validator = answer_validator(lambda: [context.to_prompt_dict(), ledger.entries])
    return await run_resilient(suite.companion, companion_prompt(question, context, viewer), CompanionAnswer,
                               validator, lambda: rule_based_answer(question, context, viewer), policy, tools)


async def personalize_recap(
    suite: AgentSuite, context: RecapContext, recap: MatchRecap, viewer: ViewerContext, policy: RunPolicy
) -> AgentOutcome[RecapTake]:
    """Ask the personalizer for one persona's take on a recap, falling back to a grounded template take."""
    evidence = [context.to_prompt_dict(), context.players, recap.model_dump(mode="json")]
    validator = take_validator(lambda: evidence, viewer.viewer.profile.max_words)
    return await run_resilient(suite.personalizer, recap_take_prompt(context, recap, viewer), RecapTake, validator,
                               lambda: template_take(context, viewer), policy)


async def translate_line(suite: AgentSuite, line: str, language: str, policy: RunPolicy) -> AgentOutcome[TranslatedLine]:
    """Translate one commentary line, keeping the original when translation fails or changes numbers."""
    return await run_resilient(suite.translator, line_translation_prompt(line, language), TranslatedLine,
                               line_translation_validator(line), lambda: TranslatedLine(line=line), policy)
