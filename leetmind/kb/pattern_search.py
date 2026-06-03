"""Keyword search over KB analyses (patterns, templates, style, techniques)."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any


def rebuild_pattern_index(conn: sqlite3.Connection) -> int:
    """Rebuild the ``pattern_docs`` FTS table from ``solution_analyses``."""
    conn.execute("DELETE FROM pattern_docs")
    rows = conn.execute("SELECT * FROM solution_analyses").fetchall()
    for r in rows:
        conn.execute(
            """
            INSERT INTO pattern_docs
                (problem_slug, title, pattern_name, core_idea, invariant,
                 techniques, pitfalls, style_notes, template_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["problem_slug"],
                r["problem_title"],
                r["pattern_name"],
                r["core_idea"],
                r["invariant"],
                " ".join(json.loads(r["techniques_json"] or "[]")),
                " ".join(json.loads(r["pitfalls_json"] or "[]")),
                " ".join(json.loads(r["style_notes_json"] or "[]")),
                r["template_code"] or "",
            ),
        )
    conn.commit()
    return len(rows)


def _fts_query(query: str) -> str:
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", query) if t]
    return " OR ".join(f'"{t}"' for t in tokens)


def search_patterns(conn: sqlite3.Connection, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Search analyses by keyword, ranked by FTS relevance (bm25)."""
    fts = _fts_query(query)
    if not fts:
        return []
    rows = conn.execute(
        """
        SELECT problem_slug, title, pattern_name, core_idea, invariant, techniques,
               bm25(pattern_docs) AS rank
        FROM pattern_docs
        WHERE pattern_docs MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (fts, limit),
    ).fetchall()
    return [
        {
            "problemSlug": r["problem_slug"],
            "title": r["title"],
            "patternName": r["pattern_name"],
            "coreIdea": r["core_idea"],
            "invariant": r["invariant"],
            "techniques": r["techniques"],
        }
        for r in rows
    ]
