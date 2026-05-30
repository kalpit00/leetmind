"""Sync the authenticated user's private/favorite lists and their membership."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from ..db.repositories import ListsRepo, MetaRepo
from ..leetcode.client import LeetCodeClient

Logger = Callable[[str], None]


def sync_lists(client: LeetCodeClient, conn: sqlite3.Connection, *, log: Logger = print) -> int:
    log("Fetching your favorite/private lists...")
    lists = client.fetch_my_lists()
    count = ListsRepo(conn).replace_all(lists)
    total_problems = sum(len(lst.question_slugs) for lst in lists)
    MetaRepo(conn).set("lists_synced", str(count))
    log(f"  cached {count} lists ({total_problems} list memberships)")
    return count
