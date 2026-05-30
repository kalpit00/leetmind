"""Typed, sanitized representations of LeetCode data.

These dataclasses deliberately contain only non-sensitive fields. They are safe
to serialize and hand to the agent. Secrets (session / csrf) never appear here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TopicTag:
    name: str
    slug: str


@dataclass
class Problem:
    frontend_id: str
    title: str
    slug: str
    difficulty: str
    paid_only: bool = False
    # "ac" if solved by the authenticated user, "notac" if attempted, None otherwise.
    status: str | None = None
    topic_tags: list[TopicTag] = field(default_factory=list)


@dataclass
class ProblemList:
    """A user-created favorite list (a.k.a. private list)."""

    slug: str
    name: str
    is_public: bool = False
    question_slugs: list[str] = field(default_factory=list)


@dataclass
class Submission:
    """A single submission summary (no code)."""

    id: str
    problem_slug: str
    problem_title: str
    status_display: str
    lang: str
    timestamp: int
    runtime: str | None = None
    memory: str | None = None
    has_notes: bool = False
    notes: str | None = None


@dataclass
class SubmissionDetail:
    """Full submission detail including code (sanitized of any auth)."""

    id: str
    problem_slug: str
    problem_title: str
    status_display: str
    lang: str
    timestamp: int
    code: str
    runtime: str | None = None
    memory: str | None = None
    notes: str | None = None
