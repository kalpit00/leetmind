"""Shared helpers for tools. Not a tool itself.

Every value returned from this module is sanitized and safe for the LLM to see.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from ..db.repositories import ListsRepo
from ..leetcode.types import Problem


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def problem_to_dict(conn: sqlite3.Connection, problem: Problem) -> dict[str, Any]:
    """Serialize a problem with its solved status and list memberships."""
    return {
        "frontendId": problem.frontend_id,
        "title": problem.title,
        "slug": problem.slug,
        "difficulty": problem.difficulty,
        "topics": [t.name for t in problem.topic_tags],
        "solved": problem.status == "ac",
        "attempted": problem.status in ("ac", "notac"),
        "lists": ListsRepo(conn).lists_for_problem(problem.slug),
    }
