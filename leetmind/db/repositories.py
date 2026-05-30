"""Data-access layer over the SQLite cache.

Repositories take a connection and expose small, intention-revealing methods.
They return plain dicts / dataclasses so callers never touch SQL.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from ..leetcode.types import Problem, ProblemList, Submission, TopicTag


def _now() -> int:
    return int(time.time())


class ProblemsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_many(self, problems: list[Problem]) -> int:
        rows = [
            (
                p.slug,
                p.frontend_id,
                p.title,
                p.difficulty,
                int(p.paid_only),
                p.status,
                json.dumps([{"name": t.name, "slug": t.slug} for t in p.topic_tags]),
                _now(),
            )
            for p in problems
        ]
        self.conn.executemany(
            """
            INSERT INTO problems
                (slug, frontend_id, title, difficulty, paid_only, status, topics_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                frontend_id = excluded.frontend_id,
                title       = excluded.title,
                difficulty  = excluded.difficulty,
                paid_only   = excluded.paid_only,
                status      = excluded.status,
                topics_json = excluded.topics_json,
                updated_at  = excluded.updated_at
            """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS c FROM problems").fetchone()["c"]

    def get_by_slug(self, slug: str) -> Problem | None:
        row = self.conn.execute("SELECT * FROM problems WHERE slug = ?", (slug,)).fetchone()
        return _problem_from_db(row) if row else None

    def get_by_frontend_id(self, frontend_id: str) -> Problem | None:
        row = self.conn.execute(
            "SELECT * FROM problems WHERE frontend_id = ?", (str(frontend_id),)
        ).fetchone()
        return _problem_from_db(row) if row else None

    def search_by_title(self, text: str, *, limit: int = 10) -> list[Problem]:
        rows = self.conn.execute(
            "SELECT * FROM problems WHERE title LIKE ? COLLATE NOCASE ORDER BY length(title) LIMIT ?",
            (f"%{text}%", limit),
        ).fetchall()
        return [_problem_from_db(r) for r in rows]

    def all(self) -> list[Problem]:
        rows = self.conn.execute("SELECT * FROM problems").fetchall()
        return [_problem_from_db(r) for r in rows]


class ListsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def replace_all(self, lists: list[ProblemList]) -> int:
        self.conn.execute("DELETE FROM lists")
        self.conn.execute("DELETE FROM list_problems")
        for lst in lists:
            self.conn.execute(
                """
                INSERT INTO lists (slug, name, is_public, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (lst.slug, lst.name, int(lst.is_public), _now()),
            )
            self.conn.executemany(
                "INSERT OR IGNORE INTO list_problems (list_slug, problem_slug) VALUES (?, ?)",
                [(lst.slug, slug) for slug in lst.question_slugs],
            )
        self.conn.commit()
        return len(lists)

    def all(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM lists ORDER BY name").fetchall()
        result = []
        for r in rows:
            count = self.conn.execute(
                "SELECT COUNT(*) AS c FROM list_problems WHERE list_slug = ?", (r["slug"],)
            ).fetchone()["c"]
            result.append(
                {
                    "slug": r["slug"],
                    "name": r["name"],
                    "is_public": bool(r["is_public"]),
                    "problem_count": count,
                }
            )
        return result

    def find(self, name_or_slug: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM lists WHERE slug = ? OR name = ? COLLATE NOCASE",
            (name_or_slug, name_or_slug),
        ).fetchone()
        if not row:
            row = self.conn.execute(
                "SELECT * FROM lists WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (f"%{name_or_slug}%",),
            ).fetchone()
        return {"slug": row["slug"], "name": row["name"], "is_public": bool(row["is_public"])} if row else None

    def lists_for_problem(self, problem_slug: str) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT l.name FROM list_problems lp
            JOIN lists l ON l.slug = lp.list_slug
            WHERE lp.problem_slug = ?
            """,
            (problem_slug,),
        ).fetchall()
        return [r["name"] for r in rows]

    def problem_slugs_in_list(self, list_slug: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT problem_slug FROM list_problems WHERE list_slug = ?", (list_slug,)
        ).fetchall()
        return [r["problem_slug"] for r in rows]


class SubmissionsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_many(self, submissions: list[Submission]) -> int:
        rows = [
            (
                s.id,
                s.problem_slug,
                s.problem_title,
                s.status_display,
                s.lang,
                s.timestamp,
                s.runtime,
                s.memory,
                int(s.has_notes),
                s.notes,
                _now(),
            )
            for s in submissions
        ]
        self.conn.executemany(
            """
            INSERT INTO submissions
                (id, problem_slug, problem_title, status_display, lang, timestamp,
                 runtime, memory, has_notes, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status_display = excluded.status_display,
                lang           = excluded.lang,
                timestamp      = excluded.timestamp,
                runtime        = excluded.runtime,
                memory         = excluded.memory,
                has_notes      = excluded.has_notes,
                notes          = excluded.notes,
                updated_at     = excluded.updated_at
            """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    def set_code(self, submission_id: str, code: str, notes: str | None = None) -> None:
        self.conn.execute(
            "UPDATE submissions SET code = ?, notes = COALESCE(?, notes), updated_at = ? WHERE id = ?",
            (code, notes, _now(), submission_id),
        )
        self.conn.commit()

    def for_problem(self, problem_slug: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM submissions WHERE problem_slug = ? ORDER BY timestamp DESC",
            (problem_slug,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, submission_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(row) if row else None

    def languages_for_problem(self, problem_slug: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT lang FROM submissions WHERE problem_slug = ? AND lang IS NOT NULL",
            (problem_slug,),
        ).fetchall()
        return [r["lang"] for r in rows]


class MetaRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def set(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, _now()),
        )
        self.conn.commit()

    def get(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def _problem_from_db(row: sqlite3.Row) -> Problem:
    topics = [TopicTag(name=t["name"], slug=t["slug"]) for t in json.loads(row["topics_json"] or "[]")]
    return Problem(
        frontend_id=row["frontend_id"] or "",
        title=row["title"],
        slug=row["slug"],
        difficulty=row["difficulty"] or "",
        paid_only=bool(row["paid_only"]),
        status=row["status"],
        topic_tags=topics,
    )
