"""Tool: resolve a free-form reference (id / slug / title) to a canonical problem."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import ProblemsRepo
from ._shared import problem_to_dict, slugify


def resolve_problem(query: str) -> dict[str, Any]:
    """Resolve a problem from a number, slug, or (partial) title.

    Returns the matched problem plus its solved status and lists. If the match
    is ambiguous, returns candidate suggestions instead.
    """
    conn = get_shared_connection()
    repo = ProblemsRepo(conn)
    q = query.strip()

    if q.isdigit():
        problem = repo.get_by_frontend_id(q)
        if problem:
            return {"found": True, "problem": problem_to_dict(conn, problem)}

    problem = repo.get_by_slug(slugify(q))
    if problem:
        return {"found": True, "problem": problem_to_dict(conn, problem)}

    matches = repo.search_by_title(q, limit=5)
    if len(matches) == 1:
        return {"found": True, "problem": problem_to_dict(conn, matches[0])}
    if matches:
        return {
            "found": False,
            "reason": "ambiguous",
            "candidates": [
                {"frontendId": m.frontend_id, "title": m.title, "slug": m.slug} for m in matches
            ],
        }
    return {"found": False, "reason": "no_match", "query": query}
