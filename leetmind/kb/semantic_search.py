"""Semantic retrieval over analyzed solution patterns.

This is intentionally local and small: embeddings are stored in SQLite as JSON
vectors, and cosine similarity is computed in Python. For a personal KB with a
few thousand solved problems, this is enough and keeps the system dependency
free. A vector DB can replace this module later without changing agent tools.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from collections.abc import Callable
from typing import Any

from .llm import get_embedding_model_name, get_openai_client

Logger = Callable[[str], None]

FIELD_WEIGHTS = {
    "patternName": 0.20,
    "techniques": 0.18,
    "coreIdea": 0.12,
    "invariant": 0.08,
    "title": 0.03,
}

IMPORTANT_TERMS = {
    "histogram": 0.18,
    "stack": 0.12,
    "monotonic": 0.10,
    "height": 0.08,
    "rectangle": 0.08,
    # Matrix/row are intentionally low-value; they are too generic and caused
    # plain matrix simulation problems to outrank real histogram-stack patterns.
    "matrix": 0.01,
    "row": 0.01,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "become",
    "becomes",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "problem",
    "the",
    "to",
    "with",
}


def analysis_embedding_text(analysis: dict[str, Any]) -> str:
    """Build the text that represents one analyzed solution for embedding."""
    parts = [
        f"Problem: {analysis.get('problem_title')}",
        f"Slug: {analysis.get('problem_slug')}",
        f"Language: {analysis.get('language')}",
        f"Pattern: {analysis.get('pattern_name')}",
        f"Techniques: {', '.join(analysis.get('techniques') or [])}",
        f"Core idea: {analysis.get('core_idea')}",
        f"Invariant: {analysis.get('invariant')}",
        f"Complexity: {analysis.get('complexity')}",
        f"Pitfalls: {'; '.join(analysis.get('pitfalls') or [])}",
        f"Style notes: {'; '.join(analysis.get('style_notes') or [])}",
        f"Template:\n{analysis.get('template_code') or ''}",
    ]
    return "\n".join(p for p in parts if p and p != "None")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_text(texts: list[str]) -> list[list[float]]:
    """Embed one or more texts using the configured embedding model."""
    client = get_openai_client()
    model = get_embedding_model_name()
    response = client.embeddings.create(model=model, input=texts)
    # The API preserves input order.
    return [item.embedding for item in response.data]


def embed_kb(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    force: bool = False,
    batch_size: int = 64,
    log: Logger = print,
) -> dict[str, int]:
    """Generate embeddings for analyzed solutions.

    Incremental: skips rows whose embedding text hash already matches the stored
    hash for the current model.
    """
    from ..db.repositories import AnalysesRepo, EmbeddingsRepo

    analyses = AnalysesRepo(conn).all()
    if limit is not None:
        analyses = analyses[:limit]
    if not analyses:
        log("No analyses found. Run `leetmind analyze-solutions` first.")
        return {"embedded": 0, "skipped": 0, "failed": 0}

    model = get_embedding_model_name()
    repo = EmbeddingsRepo(conn)
    embedded = skipped = failed = 0
    batch: list[tuple[dict[str, Any], str, str]] = []

    def flush() -> None:
        nonlocal embedded, failed
        if not batch:
            return
        texts = [item[1] for item in batch]
        try:
            vectors = embed_text(texts)
        except Exception as exc:  # noqa: BLE001 - keep counts and continue
            failed += len(batch)
            log(f"  ! failed embedding batch: {exc}")
            batch.clear()
            return
        for (analysis, _, h), vector in zip(batch, vectors, strict=True):
            repo.upsert(
                problem_slug=analysis["problem_slug"],
                embedding_model=model,
                embedding=vector,
                content_hash=h,
            )
            embedded += 1
        batch.clear()

    log(f"Embedding up to {len(analyses)} analyses (model: {model})...")
    for i, analysis in enumerate(analyses, start=1):
        text = analysis_embedding_text(analysis)
        h = content_hash(text)
        if not force and repo.existing_hash(analysis["problem_slug"], model) == h:
            skipped += 1
            continue
        batch.append((analysis, text, h))
        if len(batch) >= batch_size:
            flush()
            log(f"  {i}/{len(analyses)} processed (embedded={embedded}, skipped={skipped}, failed={failed})")
    flush()
    log(f"Done. embedded={embedded}, skipped={skipped}, failed={failed}")
    return {"embedded": embedded, "skipped": skipped, "failed": failed}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_token(token: str) -> str:
    token = token.lower()
    # Simple plural normalization is enough for terms like histograms/rows/heights.
    if len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    return token


def _tokens(text: str) -> set[str]:
    tokens = []
    for raw in re.split(r"[^a-z0-9]+", text.lower()):
        if not raw:
            continue
        token = _normalize_token(raw)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return set(tokens)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _keyword_boost(query: str, analysis: dict[str, Any]) -> tuple[float, list[str]]:
    """Domain-aware boost on top of semantic similarity.

    Embeddings can over-rank generic "matrix" problems. This reranker rewards
    exact conceptual overlap in the fields that matter most for LeetCode pattern
    transfer: pattern name, techniques, core idea, and invariant.
    """
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0.0, []

    boost = 0.0
    signals: list[str] = []
    fields = {
        "title": _text(analysis.get("problem_title")),
        "patternName": _text(analysis.get("pattern_name")),
        "techniques": _text(analysis.get("techniques")),
        "coreIdea": _text(analysis.get("core_idea")),
        "invariant": _text(analysis.get("invariant")),
    }

    for field, text in fields.items():
        overlap = q_tokens & _tokens(text)
        if not overlap:
            continue
        weight = FIELD_WEIGHTS[field]
        field_boost = min(weight, weight * len(overlap) / 2)
        boost += field_boost
        signals.append(f"{field}: {', '.join(sorted(overlap)[:4])}")

    joined = " ".join(fields.values()).lower()
    joined_tokens = _tokens(joined)
    for term, weight in IMPORTANT_TERMS.items():
        if term in q_tokens and term in joined_tokens:
            boost += weight
            signals.append(f"important term: {term}")

    # Common phrase-level bridges for matrix -> histogram problems.
    if {"histogram", "stack"} <= q_tokens and {"histogram", "stack"} <= joined_tokens:
        boost += 0.18
        signals.append("phrase: histogram + stack")

    has_histogram_intent = "histogram" in q_tokens or "height" in q_tokens
    has_histogram_evidence = "histogram" in joined_tokens or "height" in joined_tokens
    if "matrix" in q_tokens and has_histogram_intent and has_histogram_evidence:
        boost += 0.12
        signals.append("phrase: matrix -> histogram/heights")

    return min(boost, 0.7), signals


def semantic_search_by_vector(
    conn: sqlite3.Connection,
    query_vector: list[float],
    *,
    query: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search with a precomputed query vector (useful for tests and bridge)."""
    from ..db.repositories import AnalysesRepo, EmbeddingsRepo

    embeddings = EmbeddingsRepo(conn).all(get_embedding_model_name())
    analyses = AnalysesRepo(conn)
    scored = []
    for row in embeddings:
        similarity = cosine_similarity(query_vector, row["embedding"])
        analysis = analyses.get(row["problem_slug"])
        if not analysis:
            continue
        boost, signals = _keyword_boost(query, analysis)
        final_score = similarity + boost
        scored.append(
            {
                "problemSlug": analysis["problem_slug"],
                "title": analysis["problem_title"],
                "language": analysis["language"],
                "patternName": analysis["pattern_name"],
                "coreIdea": analysis["core_idea"],
                "invariant": analysis["invariant"],
                "techniques": analysis["techniques"],
                "similarity": similarity,
                "keywordBoost": boost,
                "finalScore": final_score,
                "matchedSignals": signals,
            }
        )
    scored.sort(key=lambda x: x["finalScore"], reverse=True)
    return scored[:limit]


def semantic_search_patterns(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Embed a query and search analyzed solution patterns semantically."""
    [query_vector] = embed_text([query])
    return semantic_search_by_vector(conn, query_vector, query=query, limit=limit)

