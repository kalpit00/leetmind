"""Bridge a target problem to the problems the user has already solved.

Given a problem (often unsolved), find the most related *solved* problems from
the KB and explain how to transfer their pattern/template to the target. This is
the core "Largest Rectangle in Histogram -> Maximal Rectangle" capability.

Pipeline:
  resolve target -> shortlist candidate solved analyses (keyword/topic overlap)
  -> single structured LLM call to rank bridges -> cache + return.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .schemas import BridgeResult

_SYSTEM_PROMPT = (
    "You help a user solve a new LeetCode problem by connecting it to problems "
    "they have ALREADY solved. You are given the target problem and a list of "
    "candidate solved problems (with the pattern and template the user used). "
    "Pick the candidates whose approach genuinely transfers to the target. For "
    "each, explain the relationship and concrete steps to adapt the user's known "
    "template to the target. Only use source_problem_slug values from the "
    "provided candidates. If none truly transfer, return an empty list."
)


def _shortlist_candidates(conn: sqlite3.Connection, target: dict[str, Any], k: int) -> list[dict[str, Any]]:
    """Find analyzed solved problems related to the target by topic/title."""
    from .pattern_search import search_patterns

    query_terms = list(target.get("topics", [])) + [target.get("title", "")]
    query = " ".join(t for t in query_terms if t)
    hits = search_patterns(conn, query, limit=k) if query.strip() else []

    from ..db.repositories import AnalysesRepo

    repo = AnalysesRepo(conn)
    candidates = []
    seen = set()
    for h in hits:
        slug = h["problemSlug"]
        if slug == target.get("slug") or slug in seen:
            continue
        seen.add(slug)
        analysis = repo.get(slug)
        if not analysis:
            continue
        candidates.append(
            {
                "slug": slug,
                "title": analysis["problem_title"],
                "pattern_name": analysis["pattern_name"],
                "core_idea": analysis["core_idea"],
                "techniques": analysis["techniques"],
                "template_code": analysis["template_code"],
            }
        )
    return candidates


def _build_user_prompt(target: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    lines = [
        f"TARGET problem: {target.get('title')} ({target.get('slug')})",
        f"Target topics: {', '.join(target.get('topics', [])) or 'unknown'}",
        f"Target difficulty: {target.get('difficulty') or 'unknown'}",
        "",
        "CANDIDATE solved problems (source_problem_slug must be one of these slugs):",
    ]
    for c in candidates:
        lines.append(
            f"- slug={c['slug']} | title={c['title']} | pattern={c['pattern_name']} | "
            f"techniques={', '.join(c['techniques'])}\n  core_idea: {c['core_idea']}"
        )
    return "\n".join(lines)


def bridge_problem(
    conn: sqlite3.Connection,
    target_query: str,
    *,
    max_candidates: int = 10,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Return bridges from a target problem to the user's solved problems."""
    from ..db.repositories import AnalysesRepo, BridgesRepo, ProblemsRepo

    problems = ProblemsRepo(conn)
    q = target_query.strip()
    problem = None
    if q.isdigit():
        problem = problems.get_by_frontend_id(q)
    if problem is None:
        from ..tools._shared import slugify

        problem = problems.get_by_slug(slugify(q))
    if problem is None:
        matches = problems.search_by_title(q, limit=1)
        problem = matches[0] if matches else None
    if problem is None:
        return {"found": False, "reason": "no_match", "query": target_query}

    target = {
        "slug": problem.slug,
        "title": problem.title,
        "difficulty": problem.difficulty,
        "topics": [t.name for t in problem.topic_tags],
        "solved": problem.status == "ac",
    }

    bridges_repo = BridgesRepo(conn)
    if use_cache:
        cached = bridges_repo.for_target(problem.slug)
        if cached:
            return {"found": True, "target": target, "cached": True, "bridges": _present(conn, cached)}

    candidates = _shortlist_candidates(conn, target, max_candidates)
    if not candidates:
        analyzed = AnalysesRepo(conn).count()
        reason = "no_kb" if analyzed == 0 else "no_related_solved_problems"
        return {"found": True, "target": target, "bridges": [], "reason": reason}

    result = _rank_bridges(target, candidates)
    valid_slugs = {c["slug"] for c in candidates}
    bridges = [
        {
            "source_problem_slug": b.source_problem_slug,
            "relationship": b.relationship,
            "shared_patterns": b.shared_patterns,
            "transfer_steps": b.transfer_steps,
            "confidence": b.confidence,
        }
        for b in result.bridges
        if b.source_problem_slug in valid_slugs
    ]
    bridges.sort(key=lambda b: b["confidence"], reverse=True)
    bridges_repo.replace_for_target(problem.slug, bridges)
    return {"found": True, "target": target, "cached": False, "bridges": _present(conn, bridges)}


def _present(conn: sqlite3.Connection, bridges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach source problem titles + templates for a richer tool result."""
    from ..db.repositories import AnalysesRepo

    repo = AnalysesRepo(conn)
    out = []
    for b in bridges:
        analysis = repo.get(b["source_problem_slug"])
        out.append(
            {
                "sourceProblemSlug": b["source_problem_slug"],
                "sourceTitle": analysis["problem_title"] if analysis else None,
                "sourcePattern": analysis["pattern_name"] if analysis else None,
                "relationship": b["relationship"],
                "sharedPatterns": b["shared_patterns"],
                "transferSteps": b["transfer_steps"],
                "confidence": b["confidence"],
                "sourceTemplate": analysis["template_code"] if analysis else None,
            }
        )
    return out


def _rank_bridges(target: dict[str, Any], candidates: list[dict[str, Any]]) -> BridgeResult:
    from .llm import get_model_name, get_openai_client

    client = get_openai_client()
    completion = client.beta.chat.completions.parse(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(target, candidates)},
        ],
        response_format=BridgeResult,
        temperature=0.2,
    )
    parsed = completion.choices[0].message.parsed
    return parsed if parsed is not None else BridgeResult(bridges=[])


# Re-exported for callers that only need raw json (debug CLI).
def bridge_to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2)
