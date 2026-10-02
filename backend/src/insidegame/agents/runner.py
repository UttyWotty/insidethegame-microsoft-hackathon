"""Resilient execution of a single agent call with timeout, validation, retry, and fallback.

A rejected answer is retried once with the rejection reason; a timeout falls back immediately to protect live latency.
Every outcome records its source, attempts, latency, and problems for transparency and monitoring.
"""

import asyncio
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from agent_framework import AgentFrameworkException
from pydantic import BaseModel, ValidationError

from insidegame.agents.prompts import correction_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Validator = Callable[[T], str | None]

DEFAULT_TIMEOUT_S: float = 30.0
DEFAULT_MAX_ATTEMPTS: int = 2
DEFAULT_PROMPT_SUFFIX: str = ""
MS_PER_SECOND: int = 1000
THINK_BLOCK: re.Pattern[str] = re.compile(r"<think>.*?</think>", re.DOTALL)
CODE_FENCE: re.Pattern[str] = re.compile(r"^```(?:json)?\s*|\s*```$")


class OutputSource(StrEnum):
    """Where a final agent output came from."""

    MODEL = "model"
    MODEL_RETRY = "model_retry"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class RunPolicy:
    """Execution limits for agent calls.

    Defaults: DEFAULT_TIMEOUT_S per attempt, DEFAULT_MAX_ATTEMPTS attempts, and no prompt suffix.
    """

    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    prompt_suffix: str = DEFAULT_PROMPT_SUFFIX


@dataclass(frozen=True)
class AgentOutcome(Generic[T]):
    """A validated agent output with provenance."""

    value: T
    source: OutputSource
    attempts: int
    latency_ms: int
    problems: tuple[str, ...]


class RunnableAgent(Protocol):
    """The subset of the Agent Framework Agent interface the runner needs."""

    name: str | None

    def run(self, messages: Any = None, *, tools: Any = None, options: Any = None) -> Any:
        """Run the agent on a prompt."""


def extract_json_text(text: str) -> str:
    """Strip reasoning blocks and markdown fences that some models wrap around JSON."""
    return CODE_FENCE.sub("", THINK_BLOCK.sub("", text).strip()).strip()


def _parse(response: Any, schema: type[T]) -> T:
    value = getattr(response, "value", None)
    if isinstance(value, schema):
        return value
    return schema.model_validate_json(extract_json_text(response.text))


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * MS_PER_SECOND)


async def run_resilient(
    agent: RunnableAgent, prompt: str, schema: type[T], validate: Validator[T], fallback: Callable[[], T],
    policy: RunPolicy, tools: Sequence[Any] | None = None,
) -> AgentOutcome[T]:
    """Run an agent until it returns a valid output, otherwise return the fallback."""
    start, problems, current = time.perf_counter(), [], prompt
    for attempt in range(1, policy.max_attempts + 1):
        text = f"{current}\n{policy.prompt_suffix}".strip()
        try:
            response = await asyncio.wait_for(
                agent.run(text, tools=list(tools) if tools else None, options={"response_format": schema}),
                policy.timeout_s,
            )
            value = _parse(response, schema)
            problem = validate(value)
            if problem is None:
                source = OutputSource.MODEL if attempt == 1 else OutputSource.MODEL_RETRY
                return AgentOutcome(value, source, attempt, _elapsed_ms(start), tuple(problems))
        except TimeoutError:
            problems.append(f"timed out after {policy.timeout_s}s")
            logger.warning("Agent %s timed out on attempt %d", agent.name, attempt)
            break
        except (ValidationError, ValueError, AgentFrameworkException, OSError) as exc:
            problem = f"invalid output: {exc}"
        problems.append(problem)
        logger.warning("Agent %s attempt %d rejected: %s", agent.name, attempt, problem)
        current = correction_prompt(prompt, problem)
    return AgentOutcome(fallback(), OutputSource.FALLBACK, len(problems), _elapsed_ms(start), tuple(problems))
