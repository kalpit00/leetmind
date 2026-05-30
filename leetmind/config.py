"""Central configuration loaded from environment / .env.

Security note: this module deliberately does NOT expose the LeetCode session or
CSRF tokens. Those secrets are read directly inside ``leetmind.leetcode.client``
and never travel through shared config objects or anywhere near the LLM.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_db_path() -> Path:
    """Parse DATABASE_URL (e.g. ``file:./data/leetmind.db``) into a real path."""
    raw = os.getenv("DATABASE_URL", "file:./data/leetmind.db")
    path_part = raw[len("file:"):] if raw.startswith("file:") else raw
    path = Path(path_part)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


DB_PATH: Path = _resolve_db_path()

LEETCODE_USERNAME: str = os.getenv("LEETCODE_USERNAME", "Kalpit00")

MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "openai")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
MODEL_API_KEY: str | None = os.getenv("MODEL_API_KEY")
