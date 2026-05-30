"""Authenticated LeetCode GraphQL client.

This is the ONLY module that reads ``LEETCODE_SESSION`` / ``LEETCODE_CSRF`` and
the only place that knows how to talk to leetcode.com. Everything above this
layer (sync, search, tools, agent) receives sanitized dataclasses and never sees
a cookie. Keep it that way.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from . import queries
from .types import (
    Problem,
    ProblemList,
    Submission,
    SubmissionDetail,
    TopicTag,
)

GRAPHQL_URL = "https://leetcode.com/graphql/"
BASE_URL = "https://leetcode.com"


class LeetCodeAuthError(RuntimeError):
    """Raised when the session cookie is missing or invalid."""


class LeetCodeClient:
    """Thin wrapper over LeetCode's GraphQL endpoint with cookie auth.

    Secrets are loaded from the environment at construction time and stored only
    on the private httpx client. They are never returned from any public method.
    """

    def __init__(self, *, timeout: float = 20.0, min_interval: float = 0.4) -> None:
        session = os.getenv("LEETCODE_SESSION")
        csrf = os.getenv("LEETCODE_CSRF")
        if not session or not csrf:
            raise LeetCodeAuthError(
                "LEETCODE_SESSION and LEETCODE_CSRF must be set in your environment "
                "(.env). See .env.example."
            )

        # Be polite to LeetCode: minimum delay between requests.
        self._min_interval = min_interval
        self._last_request_at = 0.0

        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Referer": BASE_URL,
                "Origin": BASE_URL,
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "x-csrftoken": csrf,
            },
            cookies={"LEETCODE_SESSION": session, "csrftoken": csrf},
        )

    # -- low level ---------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _graphql(
        self,
        query: str,
        *,
        operation_name: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._throttle()
        resp = self._client.post(
            GRAPHQL_URL,
            json={
                "query": query,
                "operationName": operation_name,
                "variables": variables or {},
            },
        )
        if resp.status_code in (401, 403):
            raise LeetCodeAuthError(
                f"LeetCode returned {resp.status_code}. Your session cookie is "
                "likely expired or invalid. Refresh LEETCODE_SESSION in .env."
            )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors for {operation_name}: {payload['errors']}")
        return payload.get("data") or {}

    # -- auth check --------------------------------------------------------

    def whoami(self) -> str | None:
        """Return the signed-in username, or None if not authenticated."""
        data = self._graphql(queries.WHOAMI, operation_name="globalData")
        status = data.get("userStatus") or {}
        return status.get("username") if status.get("isSignedIn") else None

    # -- problems ----------------------------------------------------------

    def fetch_problems(self, *, limit: int = 100) -> list[Problem]:
        """Fetch all problems (paginated) with the user's solved status."""
        problems: list[Problem] = []
        skip = 0
        total = None
        while total is None or skip < total:
            data = self._graphql(
                queries.PROBLEMSET_QUESTION_LIST,
                operation_name="problemsetQuestionList",
                variables={
                    "categorySlug": "",
                    "limit": limit,
                    "skip": skip,
                    "filters": {},
                },
            )
            block = data.get("problemsetQuestionList") or {}
            total = block.get("total", 0)
            rows = block.get("questions") or []
            if not rows:
                break
            for row in rows:
                problems.append(_problem_from_row(row))
            skip += len(rows)
        return problems

    # -- lists -------------------------------------------------------------

    def fetch_my_lists(self) -> list[ProblemList]:
        """Fetch the authenticated user's favorite (private) lists + questions."""
        data = self._graphql(queries.MY_FAVORITE_LISTS, operation_name="myCreatedFavoriteList")
        favorites = ((data.get("myCreatedFavoriteList") or {}).get("favorites")) or []
        lists: list[ProblemList] = []
        for fav in favorites:
            slug = fav.get("slug")
            if not slug:
                continue
            lists.append(
                ProblemList(
                    slug=slug,
                    name=fav.get("name", slug),
                    is_public=bool(fav.get("isPublicFavorite")),
                    question_slugs=self._fetch_list_question_slugs(slug),
                )
            )
        return lists

    def _fetch_list_question_slugs(self, favorite_slug: str, *, limit: int = 100) -> list[str]:
        slugs: list[str] = []
        skip = 0
        while True:
            data = self._graphql(
                queries.FAVORITE_QUESTION_LIST,
                operation_name="favoriteQuestionList",
                variables={"favoriteSlug": favorite_slug, "limit": limit, "skip": skip},
            )
            block = data.get("favoriteQuestionList") or {}
            questions = block.get("questions") or []
            for q in questions:
                if q.get("titleSlug"):
                    slugs.append(q["titleSlug"])
            if not block.get("hasMore") or not questions:
                break
            skip += len(questions)
        return slugs

    # -- submissions -------------------------------------------------------

    def fetch_submissions(self, problem_slug: str, *, limit: int = 20) -> list[Submission]:
        """Fetch the authenticated user's submissions for one problem."""
        data = self._graphql(
            queries.SUBMISSION_LIST,
            operation_name="submissionList",
            variables={
                "offset": 0,
                "limit": limit,
                "lastKey": None,
                "questionSlug": problem_slug,
            },
        )
        block = data.get("questionSubmissionList") or {}
        return [_submission_from_row(row, problem_slug) for row in (block.get("submissions") or [])]

    def fetch_submission_detail(self, submission_id: str) -> SubmissionDetail | None:
        """Fetch full detail (including code) for one submission."""
        data = self._graphql(
            queries.SUBMISSION_DETAILS,
            operation_name="submissionDetails",
            variables={"submissionId": int(submission_id)},
        )
        detail = data.get("submissionDetails")
        if not detail:
            return None
        return _detail_from_row(detail, submission_id)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LeetCodeClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# -- row -> dataclass mappers (keep parsing out of the request methods) ----


_shared_client: "LeetCodeClient | None" = None


def get_client() -> LeetCodeClient:
    """Lazily construct a process-wide client. Raises if cookies are missing."""
    global _shared_client
    if _shared_client is None:
        _shared_client = LeetCodeClient()
    return _shared_client


def _problem_from_row(row: dict[str, Any]) -> Problem:
    return Problem(
        frontend_id=str(row.get("frontendQuestionId", "")),
        title=row.get("title", ""),
        slug=row.get("titleSlug", ""),
        difficulty=row.get("difficulty", ""),
        paid_only=bool(row.get("paidOnly")),
        status=row.get("status"),
        topic_tags=[
            TopicTag(name=t.get("name", ""), slug=t.get("slug", ""))
            for t in (row.get("topicTags") or [])
        ],
    )


def _submission_from_row(row: dict[str, Any], problem_slug: str) -> Submission:
    return Submission(
        id=str(row.get("id", "")),
        problem_slug=row.get("titleSlug") or problem_slug,
        problem_title=row.get("title", ""),
        status_display=row.get("statusDisplay", ""),
        lang=row.get("langName") or row.get("lang", ""),
        timestamp=int(row.get("timestamp", 0)),
        runtime=row.get("runtime"),
        memory=row.get("memory"),
        has_notes=bool(row.get("hasNotes")),
        notes=row.get("notes"),
    )


def _detail_from_row(detail: dict[str, Any], submission_id: str) -> SubmissionDetail:
    question = detail.get("question") or {}
    lang = detail.get("lang") or {}
    return SubmissionDetail(
        id=submission_id,
        problem_slug=question.get("titleSlug", ""),
        problem_title=question.get("title", ""),
        status_display=str(detail.get("statusCode", "")),
        lang=lang.get("verboseName") or lang.get("name", ""),
        timestamp=int(detail.get("timestamp", 0)),
        code=detail.get("code", ""),
        runtime=detail.get("runtimeDisplay"),
        memory=detail.get("memoryDisplay"),
        notes=detail.get("notes"),
    )
