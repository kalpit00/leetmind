"""Tool: get full details (including code) for a single submission."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import SubmissionsRepo


def get_submission_details(submission_id: str) -> dict[str, Any]:
    """Return one submission's code, language, status, and notes.

    Reads from the local cache. If the code was not fetched during sync, it is
    lazily fetched from LeetCode (the session cookie stays inside the client)
    and then cached.
    """
    conn = get_shared_connection()
    repo = SubmissionsRepo(conn)
    row = repo.get(submission_id)
    if not row:
        return {"found": False, "reason": "unknown_submission", "submissionId": submission_id}

    code = row["code"]
    notes = row["notes"]
    if not code:
        code, notes = _lazy_fetch_code(repo, submission_id, notes)

    return {
        "found": True,
        "submission": {
            "id": row["id"],
            "problemSlug": row["problem_slug"],
            "problemTitle": row["problem_title"],
            "status": row["status_display"],
            "language": row["lang"],
            "timestamp": row["timestamp"],
            "runtime": row["runtime"],
            "memory": row["memory"],
            "notes": notes,
            "code": code,
        },
    }


def _lazy_fetch_code(repo: SubmissionsRepo, submission_id: str, notes: str | None):
    """Best-effort live fetch of code; returns (code, notes)."""
    try:
        from ..leetcode.client import get_client

        detail = get_client().fetch_submission_detail(submission_id)
    except Exception:
        return None, notes
    if detail and detail.code:
        repo.set_code(submission_id, detail.code, detail.notes)
        return detail.code, detail.notes or notes
    return None, notes
