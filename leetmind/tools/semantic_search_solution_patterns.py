"""Tool: semantic search over analyzed solution patterns."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..kb.semantic_search import semantic_search_patterns


def semantic_search_solution_patterns(query: str, limit: int = 8) -> dict[str, Any]:
    """Search the user's solution-pattern KB by meaning, not exact keywords.

    Use this when the user describes an idea imprecisely, asks for conceptual
    bridges, or uses different wording than the stored pattern labels. Requires
    both `leetmind analyze-solutions` and `leetmind embed-kb`.
    """
    conn = get_shared_connection()
    results = semantic_search_patterns(conn, query, limit=limit)
    return {"query": query, "count": len(results), "results": results}

