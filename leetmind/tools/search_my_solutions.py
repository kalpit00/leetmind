"""Tool: keyword-search across the user's problems, lists, and solutions."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..search.keyword_search import search


def search_my_solutions(query: str, limit: int = 8) -> dict[str, Any]:
    """Search the user's solved problems / lists / notes / code by keyword.

    Good for "recommend similar problems", "which problems used a monotonic
    stack", or "find my problems tagged dynamic programming". Returns ranked
    matches with the signals that contributed to each score.
    """
    conn = get_shared_connection()
    results = search(conn, query, limit=limit)
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "frontendId": r.doc.get("frontend_id"),
                "title": r.doc.get("title"),
                "slug": r.doc.get("slug"),
                "difficulty": r.doc.get("difficulty"),
                "solved": (r.doc.get("status") == "ac"),
                "lists": r.doc.get("lists") or "",
                "languages": r.doc.get("languages") or "",
                "score": r.score,
                "matchedOn": r.reasons,
            }
            for r in results
        ],
    }
