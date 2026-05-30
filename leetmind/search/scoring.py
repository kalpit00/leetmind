"""Custom relevance scoring on top of FTS5 candidate retrieval.

The weights follow the project's spec. FTS5 finds *candidates*; this scorer
decides final ordering using field-aware signals that plain BM25 cannot express
(e.g. an exact problem-ID or slug match should dominate).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

WEIGHT_EXACT_ID = 10
WEIGHT_EXACT_SLUG = 8
WEIGHT_ACCEPTED = 6
WEIGHT_LIST = 5
WEIGHT_TOPIC = 4
WEIGHT_NOTES = 3
WEIGHT_CODE = 2
WEIGHT_TITLE = 1


@dataclass
class ScoredDoc:
    doc: dict[str, Any]
    score: int
    reasons: list[str]


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def score_doc(query: str, doc: dict[str, Any]) -> ScoredDoc:
    q = query.strip().lower()
    q_tokens = set(_tokens(query))
    q_slug = _slugify(query)
    score = 0
    reasons: list[str] = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(reason)

    # +10 exact problem ID match (the whole query is a number matching frontend_id)
    frontend_id = str(doc.get("frontend_id", "")).strip()
    if frontend_id and (q == frontend_id or frontend_id in q_tokens):
        add(WEIGHT_EXACT_ID, f"exact problem id {frontend_id}")

    # +8 exact slug match
    slug = (doc.get("slug") or "").lower()
    if slug and (q_slug == slug or slug in q):
        add(WEIGHT_EXACT_SLUG, "exact slug match")

    # +6 accepted submission (problem is solved)
    if (doc.get("status") or "") == "ac":
        add(WEIGHT_ACCEPTED, "solved (accepted)")

    # +5 list name match
    lists_text = (doc.get("lists") or "").lower()
    if lists_text and q_tokens & set(_tokens(lists_text)):
        add(WEIGHT_LIST, "list name match")

    # +4 topic tag match
    topics_text = (doc.get("topics") or "").lower()
    if topics_text and q_tokens & set(_tokens(topics_text)):
        add(WEIGHT_TOPIC, "topic tag match")

    # +3 notes match
    notes_text = (doc.get("notes") or "").lower()
    if notes_text and q_tokens & set(_tokens(notes_text)):
        add(WEIGHT_NOTES, "notes match")

    # +2 code keyword match
    code_text = (doc.get("code") or "").lower()
    if code_text and q_tokens & set(_tokens(code_text)):
        add(WEIGHT_CODE, "code keyword match")

    # +1 title fuzzy match (any shared token)
    title_text = (doc.get("title") or "").lower()
    if title_text and q_tokens & set(_tokens(title_text)):
        add(WEIGHT_TITLE, "title match")

    return ScoredDoc(doc=doc, score=score, reasons=reasons)
