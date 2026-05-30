"""Tool: get the problems contained in a given list."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import ListsRepo, ProblemsRepo


def get_problems_in_list(list_name_or_id: str) -> dict[str, Any]:
    """Return the problems in a list, looked up by list name or slug."""
    conn = get_shared_connection()
    lists_repo = ListsRepo(conn)
    problems_repo = ProblemsRepo(conn)

    found = lists_repo.find(list_name_or_id)
    if not found:
        return {"found": False, "reason": "no_such_list", "query": list_name_or_id}

    slugs = lists_repo.problem_slugs_in_list(found["slug"])
    problems = []
    for slug in slugs:
        p = problems_repo.get_by_slug(slug)
        if p:
            problems.append(
                {
                    "frontendId": p.frontend_id,
                    "title": p.title,
                    "slug": p.slug,
                    "difficulty": p.difficulty,
                    "solved": p.status == "ac",
                }
            )
    return {
        "found": True,
        "list": {"name": found["name"], "slug": found["slug"]},
        "count": len(problems),
        "problems": problems,
    }
