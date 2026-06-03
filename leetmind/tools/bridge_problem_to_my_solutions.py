"""Tool: connect a new problem to the user's already-solved problems."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..kb.bridge import bridge_problem


def bridge_problem_to_my_solutions(problem: str, refresh: bool = False) -> dict[str, Any]:
    """Find which solved problems the given problem is most related to.

    This is the core "help me solve X using what I already know" capability.
    Given a problem (number, slug, or title), it returns the user's solved
    problems whose pattern/template transfers to it, with concrete adaptation
    steps and the reusable template code. Pass refresh=True to ignore a cached
    bridge and recompute candidates. Requires `leetmind analyze-solutions`.
    """
    conn = get_shared_connection()
    return bridge_problem(conn, problem, use_cache=not refresh)
