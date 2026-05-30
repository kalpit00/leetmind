"""Sync all problem metadata (title, slug, id, difficulty, topics, status)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from ..db.repositories import MetaRepo, ProblemsRepo
from ..leetcode.client import LeetCodeClient

Logger = Callable[[str], None]


def sync_problems(client: LeetCodeClient, conn: sqlite3.Connection, *, log: Logger = print) -> int:
    log("Fetching problem catalog from LeetCode (paginated)...")
    problems = client.fetch_problems()
    count = ProblemsRepo(conn).upsert_many(problems)
    MetaRepo(conn).set("problems_synced", str(count))
    log(f"  cached {count} problems")
    return count
