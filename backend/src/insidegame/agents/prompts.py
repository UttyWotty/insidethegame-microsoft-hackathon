"""System instructions and prompt builders for each specialised agent.

Every agent has one narrow role, and all share the same grounding rule: cite only numbers present in the input.
Prompt builders serialise context as JSON so the model sees exactly the evidence the grounding check will accept.
"""

import json

from insidegame.agents.context import MomentContext, ViewerContext
from insidegame.agents.glossary import concept_for
from insidegame.agents.personas import PersonaKey
from insidegame.agents.question_context import QuestionContext
from insidegame.agents.recap_context import RecapContext
from insidegame.agents.schemas import Explanation, MatchRecap, PersonaCard

GROUNDING_RULE: str = (
    "Use only names and numbers that appear in the input JSON or in your tool results. "
    "Never invent statistics, minutes, or players. Reply with JSON matching the requested schema only."
)

ANALYST_INSTRUCTIONS: str = (
    "You are the Match Analyst for a live football broadcast. Explain why a key moment matters for the match: "
    "its consequence, the tactical pattern behind it (control, chaos, pressure shifts, individual quality), "
    "and the evidence. Do not simply restate what happened. You may call tools to look up player or team "
    f"statistics. {GROUNDING_RULE}"
)

NARRATOR_INSTRUCTIONS: str = (
    "You are the Lead Commentator. Turn the analyst's explanation into one vivid, broadcast-ready line that "
    f"could be spoken live over the pictures. Keep it under 30 words. {GROUNDING_RULE}"
)

PERSONALIZER_INSTRUCTIONS: str = (
    "You are the Personalization Producer. Rewrite the analyst's explanation as an on-screen card for one "
    "specific viewer persona. Follow the persona's voice, vocabulary, perspective, and word budget exactly; "
    f"the same moment must feel genuinely different for each persona. {GROUNDING_RULE}"
)

TRANSLATOR_INSTRUCTIONS: str = (
    "You are a broadcast translator. Translate the card into the target language with natural football "
    "phrasing used by commentators in that market. Keep player names, club names, and every number unchanged. "
    "Reply with JSON matching the requested schema only."
)

FACT_CHECKER_INSTRUCTIONS: str = (
    "You are the Broadcast Standards Editor. Before anything goes to air, check a draft against the facts JSON. "
    "Reject it if it attributes an action to the wrong player or team, describes an outcome that did not happen "
    "(for example a goal that was saved or missed), invents events or statistics, or is disrespectful. Style and "
    "persona voice are not errors. Approve accurate drafts. Reply with JSON matching the requested schema only."
)

COMPANION_INSTRUCTIONS: str = (
    "You are the Match Companion, answering one viewer's question during a live football broadcast. Answer only "
    "questions about this match, in the viewer's persona voice and requested language. If a question is unrelated, "
    "asks for betting advice, or is inappropriate, decline in one friendly sentence and suggest a match question. "
    f"Use tools for player or team details not in the input. {GROUNDING_RULE}"
)

RECAP_INSTRUCTIONS: str = (
    "You are the Match Editor. Write an automated match recap for studio and streaming use from the key "
    f"moments and statistics provided. Tell the story of the match, not a list of events. {GROUNDING_RULE}"
)


def _dump(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def analyst_prompt(context: MomentContext) -> str:
    """Prompt asking the analyst to explain one moment."""
    return f"Explain this key moment.\n{_dump(context.to_prompt_dict())}"


def narrator_prompt(context: MomentContext, explanation: Explanation) -> str:
    """Prompt asking the narrator for a commentary line."""
    payload = {"minute": context.moment.minute_label, "explanation": explanation.model_dump(mode="json"),
               "facts": dict(context.moment.facts)}
    return f"Write the commentary line.\n{_dump(payload)}"


def _persona_brief(viewer: ViewerContext) -> dict[str, object]:
    profile = viewer.viewer.profile
    brief: dict[str, object] = {
        "persona": profile.display_name, "audience": profile.audience, "voice": profile.voice,
        "vocabulary": profile.vocabulary, "max_words": profile.max_words,
        "perspective": profile.perspective.value, "stat_focus": list(profile.stat_focus),
    }
    if viewer.viewer.persona is PersonaKey.SUPERFAN:
        brief["favourite_club"] = viewer.favourite_team_name
    if viewer.viewer.persona is PersonaKey.PLAYER_TRACKER:
        brief["tracked_player"] = viewer.tracked_player_name
        brief["framing"] = (f"Write from {viewer.tracked_player_name}'s point of view. If they were not involved, "
                            "say how the moment affects them, citing their own statistics from context.players.")
    return brief


def personalizer_prompt(context: MomentContext, explanation: Explanation, viewer: ViewerContext) -> str:
    """Prompt asking the personalizer for one persona's card."""
    payload: dict[str, object] = {
        "persona_brief": _persona_brief(viewer),
        "explanation": explanation.model_dump(mode="json"),
        "context": context.to_prompt_dict(),
    }
    if viewer.viewer.profile.explains_terms:
        term, meaning = concept_for(context.moment.kind)
        payload["concept_to_teach"] = {"term": term, "meaning": meaning}
    return f"Create the card for this persona.\n{_dump(payload)}"


def translator_prompt(card: PersonaCard, language: str) -> str:
    """Prompt asking the translator to localise a card."""
    payload = {"target_language": language, "title": card.title, "body": card.body,
               "stat_labels": [c.label for c in card.stat_callouts]}
    return f"Translate this card.\n{_dump(payload)}"


def correction_prompt(original_prompt: str, problem: str) -> str:
    """Prompt asking an agent to fix a rejected answer."""
    return f"{original_prompt}\nYour previous answer was rejected: {problem}. Fix it and answer again."


def recap_prompt(context: RecapContext) -> str:
    """Prompt asking the editor for a half-time or full-time recap."""
    return f"Write the {context.stage.value.replace('_', '-')} recap.\n{_dump(context.to_prompt_dict())}"


def companion_prompt(question: str, context: QuestionContext, viewer: ViewerContext) -> str:
    """Prompt asking the Match Companion to answer a viewer's question."""
    payload = {"question": question, "answer_language": viewer.viewer.language,
               "persona_brief": _persona_brief(viewer), "match": context.to_prompt_dict()}
    return f"Answer the viewer's question.\n{_dump(payload)}"


def recap_take_prompt(context: RecapContext, recap: MatchRecap, viewer: ViewerContext) -> str:
    """Prompt asking the personalizer for one persona's take on a recap."""
    payload: dict[str, object] = {"persona_brief": _persona_brief(viewer), "write_in_language": viewer.viewer.language,
                                  "recap": recap.model_dump(mode="json"), "match": context.to_prompt_dict()}
    if viewer.tracked_player_name:
        payload["tracked_player_stats"] = context.players.get(viewer.tracked_player_name, {})
    return f"Write this persona's take on the {context.stage.value.replace('_', '-')} recap.\n{_dump(payload)}"


def line_translation_prompt(line: str, language: str) -> str:
    """Prompt asking the translator to localise one commentary line."""
    return f"Translate this commentary line.\n{_dump({'target_language': language, 'line': line})}"


def fact_check_prompt(context: MomentContext, explanation: Explanation, draft_kind: str, draft: str) -> str:
    """Prompt asking the fact-checker to approve or reject one draft."""
    payload = {"draft_kind": draft_kind, "draft": draft, "facts": context.to_prompt_dict(),
               "analyst_explanation": explanation.model_dump(mode="json")}
    return f"Check this draft before it goes to air.\n{_dump(payload)}"
