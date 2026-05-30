"""Sync submissions for solved problems, optionally fetching code for each.

This is the most expensive sync (one+ API call per solved problem), so it is
throttled by the client and bounded by ``limit``. By default it also pulls the
code of the most recent Accepted submission per problem so the agent can reason
about *how* a problem was solved.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from ..db.repositories import MetaRepo, ProblemsRepo, SubmissionsRepo
from ..leetcode.client import LeetCodeClient

Logger = Callable[[str], None]


def sync_submissions(
    client: LeetCodeClient,
    conn: sqlite3.Connection,
    *,
    fetch_code: bool = True,
    limit: int | None = None,
    log: Logger = print,
) -> int:
    problems = ProblemsRepo(conn).all()
    solved = [p for p in problems if p.status == "ac"]
    if limit is not None:
        solved = solved[:limit]

    if not solved:
        log("No solved problems found in cache. Run problem sync first.")
        return 0

    log(f"Syncing submissions for {len(solved)} solved problems...")
    subs_repo = SubmissionsRepo(conn)
    total = 0
    for i, problem in enumerate(solved, start=1):
        submissions = client.fetch_submissions(problem.slug)
        if submissions:
            subs_repo.upsert_many(submissions)
            total += len(submissions)
        if fetch_code:
            _fetch_code_for_best(client, subs_repo, submissions)
        if i % 25 == 0 or i == len(solved):
            log(f"  {i}/{len(solved)} problems ({total} submissions)")

    MetaRepo(conn).set("submissions_synced", str(total))
    log(f"  cached {total} submissions")
    return total


def _fetch_code_for_best(client: LeetCodeClient, subs_repo: SubmissionsRepo, submissions: list) -> None:
    """Fetch + store code for the most recent Accepted submission, if any."""
    accepted = next((s for s in submissions if s.status_display == "Accepted"), None)
    if accepted is None:
        return
    detail = client.fetch_submission_detail(accepted.id)
    if detail and detail.code:
        subs_repo.set_code(accepted.id, detail.code, detail.notes)
