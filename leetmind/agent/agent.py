"""Construct and run the Leetmind agent via the OpenAI Agents SDK."""

from __future__ import annotations

import os

from agents import Agent, RunHooks, Runner

from ..config import MODEL_API_KEY, MODEL_NAME
from .system_prompt import SYSTEM_PROMPT
from .tool_registry import TOOLS


def _ensure_api_key() -> None:
    """The SDK reads OPENAI_API_KEY; map our MODEL_API_KEY onto it."""
    if MODEL_API_KEY and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = MODEL_API_KEY


def build_agent() -> Agent:
    _ensure_api_key()
    return Agent(
        name="Leetmind",
        instructions=SYSTEM_PROMPT,
        model=MODEL_NAME,
        tools=TOOLS,
    )


def ask_once(question: str, *, hooks: RunHooks | None = None) -> str:
    """Single-shot question -> final answer string.

    Pass ``hooks`` (e.g. ConsoleTraceHooks) to surface the tool-calling trace.
    """
    result = Runner.run_sync(build_agent(), question, hooks=hooks)
    return result.final_output


class Conversation:
    """Stateful multi-turn wrapper that preserves history between turns."""

    def __init__(self, hooks: RunHooks | None = None) -> None:
        self._agent = build_agent()
        self._history: list = []
        self._hooks = hooks

    def send(self, message: str) -> str:
        turn_input = self._history + [{"role": "user", "content": message}]
        result = Runner.run_sync(self._agent, turn_input, hooks=self._hooks)
        self._history = result.to_input_list()
        return result.final_output
