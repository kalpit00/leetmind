"""SQLite connection management and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import DB_PATH

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sensible defaults and ensure schema exists."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


_shared_conn: sqlite3.Connection | None = None


def get_shared_connection() -> sqlite3.Connection:
    """Process-wide cached connection, used by the read-only agent tools."""
    global _shared_conn
    if _shared_conn is None:
        _shared_conn = get_connection()
    return _shared_conn
