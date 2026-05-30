"""Keyword search: build a denormalized FTS5 index and rank with custom scoring."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .scoring import ScoredDoc, score_doc


def rebuild_index(conn: sqlite3.Connection) -> int:
    """Rebuild the per-problem search documents from the cached tables.

    Each document denormalizes a problem together with the lists it belongs to
    and an aggregate of its submissions (languages, notes, code).
    """
    conn.execute("DELETE FROM search_docs")

    problems = conn.execute("SELECT * FROM problems").fetchall()
    count = 0
    for p in problems:
        slug = p["slug"]
        topics = [t["name"] for t in json.loads(p["topics_json"] or "[]")]

        list_names = [
            r["name"]
            for r in conn.execute(
                """
                SELECT l.name FROM list_problems lp
                JOIN lists l ON l.slug = lp.list_slug
                WHERE lp.problem_slug = ?
                """,
                (slug,),
            ).fetchall()
        ]

        subs = conn.execute(
            "SELECT lang, notes, code FROM submissions WHERE problem_slug = ?", (slug,)
        ).fetchall()
        languages = sorted({s["lang"] for s in subs if s["lang"]})
        notes = " ".join(s["notes"] for s in subs if s["notes"])
        code = " ".join(s["code"] for s in subs if s["code"])

        conn.execute(
            """
            INSERT INTO search_docs
                (slug, frontend_id, title, difficulty, topics, lists, status, languages, notes, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                p["frontend_id"],
                p["title"],
                p["difficulty"],
                " ".join(topics),
                " ".join(list_names),
                p["status"],
                " ".join(languages),
                notes,
                code,
            ),
        )
        count += 1

    conn.commit()
    return count


def _fts_query(query: str) -> str:
    """Turn a free-text query into a safe FTS5 OR-expression."""
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", query) if t]
    return " OR ".join(f'"{t}"' for t in tokens)


def search(conn: sqlite3.Connection, query: str, *, limit: int = 10) -> list[ScoredDoc]:
    """Retrieve FTS candidates then re-rank with the custom field-aware scorer."""
    fts = _fts_query(query)
    candidates: list[dict[str, Any]] = []

    if fts:
        rows = conn.execute(
            """
            SELECT slug, frontend_id, title, difficulty, topics, lists, status, languages, notes, code
            FROM search_docs
            WHERE search_docs MATCH ?
            LIMIT 200
            """,
            (fts,),
        ).fetchall()
        candidates = [dict(r) for r in rows]

    # Fallback: if FTS found nothing (e.g. pure numeric id), scan a bounded set.
    if not candidates:
        rows = conn.execute(
            """
            SELECT slug, frontend_id, title, difficulty, topics, lists, status, languages, notes, code
            FROM search_docs LIMIT 200
            """
        ).fetchall()
        candidates = [dict(r) for r in rows]

    scored = [score_doc(query, doc) for doc in candidates]
    scored = [s for s in scored if s.score > 0]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]
