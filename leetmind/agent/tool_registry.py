"""Wrap the plain tool functions as OpenAI Agents SDK function tools.

The underlying functions live in ``leetmind.tools`` and return sanitized JSON.
Here we only adapt them into the SDK's tool schema (derived from type hints +
docstrings). Keeping the wrapping separate means the tools stay framework-free
and independently testable.
"""

from __future__ import annotations

from agents import function_tool

from ..tools.bridge_problem_to_my_solutions import bridge_problem_to_my_solutions
from ..tools.get_coding_style_profile import get_coding_style_profile
from ..tools.get_my_lists import get_my_lists
from ..tools.get_my_submissions import get_my_submissions
from ..tools.get_problems_in_list import get_problems_in_list
from ..tools.get_solution_pattern import get_solution_pattern
from ..tools.get_submission_details import get_submission_details
from ..tools.resolve_problem import resolve_problem
from ..tools.search_my_solutions import search_my_solutions
from ..tools.search_solution_patterns import search_solution_patterns
from ..tools.semantic_search_solution_patterns import semantic_search_solution_patterns

TOOLS = [
    # Core profile tools (raw LeetCode cache).
    function_tool(resolve_problem),
    function_tool(get_my_lists),
    function_tool(get_problems_in_list),
    function_tool(get_my_submissions),
    function_tool(get_submission_details),
    function_tool(search_my_solutions),
    # Knowledge-base tools (distilled from analyzed submissions).
    function_tool(get_solution_pattern),
    function_tool(search_solution_patterns),
    function_tool(semantic_search_solution_patterns),
    function_tool(get_coding_style_profile),
    function_tool(bridge_problem_to_my_solutions),
]
