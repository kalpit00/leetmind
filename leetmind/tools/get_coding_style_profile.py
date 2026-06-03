"""Tool: summarize the user's coding-style profile from the knowledge base."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..kb.style_profile import build_style_profile


def get_coding_style_profile() -> dict[str, Any]:
    """Return how the user tends to write code, aggregated across solutions.

    Reports preferred languages, recurring style traits (naming, chosen data
    structures, iterative vs recursive, formatting), and most-used techniques.
    Use this to phrase suggestions in the user's own style. Requires
    `leetmind analyze-solutions` to have been run.
    """
    conn = get_shared_connection()
    profile = build_style_profile(conn)
    if profile.get("analyzed", 0) == 0:
        return {"found": False, "reason": "no_kb", **profile}
    return {"found": True, **profile}
