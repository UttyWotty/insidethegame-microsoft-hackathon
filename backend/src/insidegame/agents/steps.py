"""One resilient operation per agent role: explain, narrate, personalize, and translate.

Each step builds its prompt, evidence, validator, and fallback, then delegates to run_resilient.
Orchestration executors call these steps so workflow wiring stays separate from agent behaviour.
"""

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.factory import AgentSuite
from insidegame.agents.prompts import analyst_prompt, narrator_prompt, personalizer_prompt, translator_prompt
from insidegame.agents.runner import AgentOutcome, RunPolicy, run_resilient
from insidegame.agents.schemas import Commentary, Explanation, PersonaCard, TranslatedCard
from insidegame.agents.templates import (
    commentary_template,
    explanation_template,
    persona_card_template,
    untranslated_card,
)
from insidegame.agents.tools import EvidenceLedger, build_analyst_tools
from insidegame.agents.validation import (
    card_validator,
    commentary_validator,
    explanation_validator,
    translation_validator,
)
from insidegame.analytics.analyzer import MatchAnalyzer


async def explain(
    suite: AgentSuite, context: MomentContext, analyzer: MatchAnalyzer, policy: RunPolicy
) -> AgentOutcome[Explanation]:
    """Ask the analyst why the moment matters, allowing statistics tool calls."""
    ledger = EvidenceLedger()
    tools = build_analyst_tools(analyzer, ledger)
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
