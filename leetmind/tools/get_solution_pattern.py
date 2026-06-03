"""Tool: get the analyzed pattern/template for one solved problem."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import AnalysesRepo
from ._shared import slugify


def get_solution_pattern(problem_slug: str) -> dict[str, Any]:
    """Return the knowledge-base analysis for a solved problem.

    Includes the pattern name, core idea, invariant, complexity, pitfalls, the
    reusable code template, and observed coding-style traits. Requires that
    `leetmind analyze-solutions` has been run. Accepts a slug or title.
    """
    conn = get_shared_connection()
    repo = AnalysesRepo(conn)
    analysis = repo.get(problem_slug) or repo.get(slugify(problem_slug))
    if not analysis:
        return {"found": False, "reason": "not_analyzed", "problemSlug": problem_slug}
    return {
        "found": True,
        "pattern": {
            "problemSlug": analysis["problem_slug"],
            "title": analysis["problem_title"],
            "language": analysis["language"],
            "patternName": analysis["pattern_name"],
            "coreIdea": analysis["core_idea"],
            "invariant": analysis["invariant"],
            "complexity": analysis["complexity"],
            "techniques": analysis["techniques"],
            "pitfalls": analysis["pitfalls"],
            "templateCode": analysis["template_code"],
            "styleNotes": analysis["style_notes"],
        },
    }
