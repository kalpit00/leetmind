"""Run hooks that surface the agent's tool-calling orchestration in real time.

This is what makes the agentic workflow *visible* (and screenshot-friendly): each
time the agent decides to call a tool, we print the call and a short summary of
the sanitized result. It also reports agent hand-offs, so the same trace works if
the project grows into a multi-agent (handoff) setup.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from agents import RunHooks

# emit(text, kind) -> None. kind is a style hint the CLI can color.
Emit = Callable[[str, str], None]


def _plain(text: str, kind: str) -> None:  # noqa: ARG001 - default emitter ignores kind
    print(text)


class ConsoleTraceHooks(RunHooks):
    """Prints an ordered, indented trace of tool calls during a run."""

    def __init__(self, emit: Emit = _plain) -> None:
        self.emit = emit
        self.step = 0

    async def on_tool_start(self, context, agent, tool) -> None:  # noqa: ANN001
        self.step += 1
        raw_args = getattr(context, "tool_arguments", None) or getattr(context, "tool_input", None)
        self.emit(f"  step {self.step}  call  {tool.name}({_format_args(raw_args)})", "tool")

    async def on_tool_end(self, context, agent, tool, result) -> None:  # noqa: ANN001
        self.emit(f"           result  {_summarize(result)}", "result")

    async def on_handoff(self, context, from_agent, to_agent) -> None:  # noqa: ANN001
        self.emit(f"  handoff  {from_agent.name} -> {to_agent.name}", "handoff")


def _format_args(tool_input) -> str:  # noqa: ANN001
    """Render tool arguments compactly as key=value pairs."""
    data = tool_input
    if isinstance(tool_input, str):
        try:
            data = json.loads(tool_input)
        except (ValueError, TypeError):
            return tool_input[:80]
    if isinstance(data, dict):
        return ", ".join(f"{k}={_short(v)}" for k, v in data.items())
    return _short(data)


def _summarize(result) -> str:  # noqa: ANN001
    """Summarize a tool's JSON result into a one-liner."""
    data = result
    if isinstance(result, str):
        try:
            data = json.loads(result)
        except (ValueError, TypeError):
            return result[:120]
    if isinstance(data, dict):
        parts = []
        for key in ("found", "count", "query"):
            if key in data:
                parts.append(f"{key}={_short(data[key])}")
        if "problem" in data and isinstance(data["problem"], dict):
            p = data["problem"]
            parts.append(f"problem='{p.get('title')}' solved={p.get('solved')}")
        if "lists" in data and isinstance(data["lists"], list):
            parts.append(f"lists={len(data['lists'])}")
        if "results" in data and isinstance(data["results"], list):
            top = data["results"][0]["title"] if data["results"] else None
            parts.append(f"top='{top}'")
        return ", ".join(parts) if parts else _short(data)
    return _short(data)


def _short(value, limit: int = 48) -> str:  # noqa: ANN001
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"
