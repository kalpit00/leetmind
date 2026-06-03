"""Aggregate the user's coding-style profile from per-submission style notes.

This is pure aggregation over already-analyzed rows (no LLM call): it counts
recurring style traits, languages, and techniques so the agent can describe how
the user tends to write code and reuse that voice in suggestions.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from typing import Any


def _normalize(note: str) -> str:
    return re.sub(r"\s+", " ", note.strip().lower())


def build_style_profile(conn: sqlite3.Connection, *, top: int = 12) -> dict[str, Any]:
    """Summarize recurring style traits, languages, and techniques."""
    from ..db.repositories import AnalysesRepo

    analyses = AnalysesRepo(conn).all()
    if not analyses:
        return {"analyzed": 0, "languages": [], "topStyleTraits": [], "topTechniques": []}

    style_counter: Counter[str] = Counter()
    technique_counter: Counter[str] = Counter()
    language_counter: Counter[str] = Counter()

    for a in analyses:
        if a.get("language"):
            language_counter[a["language"]] += 1
        for note in a.get("style_notes", []):
            if note:
                style_counter[_normalize(note)] += 1
        for tech in a.get("techniques", []):
            if tech:
                technique_counter[_normalize(tech)] += 1

    return {
        "analyzed": len(analyses),
        "languages": [
            {"language": lang, "count": n} for lang, n in language_counter.most_common()
        ],
        "topStyleTraits": [
            {"trait": trait, "count": n} for trait, n in style_counter.most_common(top)
        ],
        "topTechniques": [
            {"technique": tech, "count": n} for tech, n in technique_counter.most_common(top)
        ],
    }
