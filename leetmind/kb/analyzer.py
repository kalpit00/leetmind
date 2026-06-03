"""Offline analysis pipeline: turn accepted submissions into structured KB rows.

For each accepted submission that has code cached, ask the LLM to extract the
pattern, invariant, complexity, a reusable template, technique labels, and the
user's coding-style traits. Results are stored in ``solution_analyses``.

Incremental by design: a submission whose code hash already matches the current
``ANALYSIS_VERSION`` is skipped, so re-running is cheap and only processes new
or changed solutions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable

from . import ANALYSIS_VERSION
from .schemas import SolutionAnalysis

Logger = Callable[[str], None]

_SYSTEM_PROMPT = (
    "You are a senior competitive-programming mentor analyzing one of a user's "
    "ACCEPTED LeetCode submissions. Extract the reusable knowledge from THIS "
    "specific code: the core pattern, its invariant, complexity, a generalized "
    "reusable template in the same language, technique labels, pitfalls, and the "
    "user's observable coding-style traits. Ground everything in the code shown; "
    "do not invent techniques the code does not use."
)


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _candidate_rows(conn: sqlite3.Connection, limit: int | None) -> list[sqlite3.Row]:
    """Accepted submissions that have code, joined with problem metadata.

    One representative (most recent accepted) submission per problem.
    """
    sql = """
        SELECT s.id              AS submission_id,
               s.problem_slug    AS problem_slug,
               s.problem_title   AS problem_title,
               s.lang            AS language,
               s.code            AS code,
               s.notes           AS notes,
               s.timestamp       AS timestamp,
               p.difficulty      AS difficulty,
               p.topics_json     AS topics_json
        FROM submissions s
        LEFT JOIN problems p ON p.slug = s.problem_slug
        WHERE s.status_display = 'Accepted'
          AND s.code IS NOT NULL AND s.code != ''
        GROUP BY s.problem_slug
        HAVING s.timestamp = MAX(s.timestamp)
        ORDER BY s.problem_slug
    """
    if limit is not None:
        sql += " LIMIT ?"
        return conn.execute(sql, (limit,)).fetchall()
    return conn.execute(sql).fetchall()


def _build_user_prompt(row: sqlite3.Row) -> str:
    topics = [t.get("name") for t in json.loads(row["topics_json"] or "[]")]
    parts = [
        f"Problem: {row['problem_title']} ({row['problem_slug']})",
        f"Difficulty: {row['difficulty'] or 'Unknown'}",
        f"LeetCode topic tags: {', '.join(topics) if topics else 'none'}",
        f"Language: {row['language']}",
    ]
    if row["notes"]:
        parts.append(f"User notes: {row['notes']}")
    parts.append("\nAccepted solution code:\n```\n" + (row["code"] or "") + "\n```")
    return "\n".join(parts)


def analyze_solutions(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    force: bool = False,
    log: Logger = print,
) -> dict[str, int]:
    """Analyze accepted submissions into the KB. Returns counts.

    Skips submissions already analyzed at the current version with unchanged
    code unless ``force`` is set.
    """
    from ..db.repositories import AnalysesRepo
    from .llm import get_model_name, get_openai_client
    from .pattern_search import rebuild_pattern_index

    rows = _candidate_rows(conn, limit)
    if not rows:
        log("No accepted submissions with code found. Run `leetmind sync` first.")
        return {"analyzed": 0, "skipped": 0, "failed": 0}

    repo = AnalysesRepo(conn)
    client = get_openai_client()
    model = get_model_name()

    analyzed = skipped = failed = 0
    log(f"Analyzing up to {len(rows)} solved problems (model: {model})...")
    for i, row in enumerate(rows, start=1):
        slug = row["problem_slug"]
        code_hash = _code_hash(row["code"] or "")

        if not force and repo.existing_hash(slug, ANALYSIS_VERSION) == code_hash:
            skipped += 1
            continue

        try:
            analysis = _analyze_one(client, model, row)
        except Exception as exc:  # noqa: BLE001 - keep going on individual failures
            failed += 1
            log(f"  ! failed {slug}: {exc}")
            continue

        repo.upsert(
            {
                "problem_slug": slug,
                "submission_id": row["submission_id"],
                "problem_title": row["problem_title"],
                "language": row["language"],
                "pattern_name": analysis.pattern_name,
                "core_idea": analysis.core_idea,
                "invariant": analysis.invariant,
                "complexity": analysis.complexity,
                "pitfalls": analysis.pitfalls,
                "template_code": analysis.template_code,
                "style_notes": analysis.style_notes,
                "techniques": analysis.techniques,
                "code_hash": code_hash,
                "analysis_version": ANALYSIS_VERSION,
            }
        )
        analyzed += 1
        if analyzed % 10 == 0 or i == len(rows):
            log(f"  {i}/{len(rows)} processed (analyzed={analyzed}, skipped={skipped}, failed={failed})")

    log("Rebuilding pattern search index...")
    indexed = rebuild_pattern_index(conn)
    log(f"  indexed {indexed} analyses")
    return {"analyzed": analyzed, "skipped": skipped, "failed": failed}


def _analyze_one(client, model: str, row: sqlite3.Row) -> SolutionAnalysis:
    """Single structured LLM call for one submission."""
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(row)},
        ],
        response_format=SolutionAnalysis,
        temperature=0.2,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("model returned no parsed analysis")
    return parsed
