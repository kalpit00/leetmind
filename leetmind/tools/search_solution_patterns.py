"""Tool: keyword-search the knowledge base of analyzed solution patterns."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..kb.pattern_search import search_patterns


def search_solution_patterns(query: str, limit: int = 8) -> dict[str, Any]:
    """Search the user's analyzed solutions by pattern, technique, or idea.

    Unlike `search_my_solutions` (which matches raw titles/lists/code), this
    searches the distilled knowledge base: pattern names, core ideas,
    invariants, and techniques. Use it for questions like "which of my problems
    use a monotonic stack" or "show my sliding window patterns". Requires
    `leetmind analyze-solutions` to have been run.
    """
    conn = get_shared_connection()
    results = search_patterns(conn, query, limit=limit)
    return {"query": query, "count": len(results), "results": results}
