"""Tool: get the user's submissions for a problem (summaries, no code)."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import SubmissionsRepo


def get_my_submissions(problem_slug: str) -> dict[str, Any]:
    """Return submission summaries for one problem (status, language, time).

    Use ``resolve_problem`` first if you only have a title or number; this tool
    expects the canonical slug (e.g. "two-sum"). Code is not included here; use
    ``get_submission_details`` for that.
    """
    conn = get_shared_connection()
    rows = SubmissionsRepo(conn).for_problem(problem_slug)
    submissions = [
        {
            "id": r["id"],
            "status": r["status_display"],
            "language": r["lang"],
            "timestamp": r["timestamp"],
            "hasNotes": bool(r["has_notes"]),
            "hasCode": bool(r["code"]),
        }
        for r in rows
    ]
    return {"problemSlug": problem_slug, "count": len(submissions), "submissions": submissions}
