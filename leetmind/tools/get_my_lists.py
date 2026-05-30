"""Tool: list the user's private/favorite lists."""

from __future__ import annotations

from typing import Any

from ..db.database import get_shared_connection
from ..db.repositories import ListsRepo


def get_my_lists() -> dict[str, Any]:
    """Return all of the user's saved lists with a problem count for each."""
    conn = get_shared_connection()
    return {"lists": ListsRepo(conn).all()}
