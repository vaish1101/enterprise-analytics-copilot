from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from threading import Lock
from uuid import uuid4


class SessionStore:
    """Stores safe structured responses, never prompts, secrets, or raw documents."""

    def __init__(self, path: str | None = None):
        self.path = path
        self._lock = Lock()
        self._memory: dict[str, list[dict]] = {}
        self._postgres = bool(path and path.startswith(("postgresql://", "postgres://")))
        if self._postgres:
            import psycopg  # type: ignore[import-not-found]
            with psycopg.connect(path) as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS api_session_interactions (
                        session_id text NOT NULL,
                        created_at timestamptz NOT NULL,
                        payload jsonb NOT NULL
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS api_session_interactions_lookup_idx "
                    "ON api_session_interactions (session_id, created_at)"
                )
            self._connection = None
        elif path:
            resolved = Path(path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(resolved, check_same_thread=False)
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS interactions (session_id TEXT, created_at TEXT, payload TEXT)"
            )
            self._connection.commit()
        else:
            self._connection = None

    @staticmethod
    def new_id() -> str:
        return f"session_{uuid4().hex[:20]}"

    def append(self, session_id: str, payload: dict) -> None:
        record = {"created_at": datetime.now(UTC).isoformat(), **payload}
        with self._lock:
            if self._postgres:
                import psycopg  # type: ignore[import-not-found]
                from psycopg.types.json import Jsonb  # type: ignore[import-not-found]
                with psycopg.connect(self.path) as connection:
                    connection.execute(
                        "INSERT INTO api_session_interactions VALUES (%s, %s, %s)",
                        (session_id, record["created_at"], Jsonb(record)),
                    )
            elif self._connection:
                self._connection.execute(
                    "INSERT INTO interactions VALUES (?, ?, ?)",
                    (session_id, record["created_at"], json.dumps(record, sort_keys=True)),
                )
                self._connection.commit()
            else:
                self._memory.setdefault(session_id, []).append(record)

    def get(self, session_id: str) -> list[dict]:
        with self._lock:
            if self._postgres:
                import psycopg  # type: ignore[import-not-found]
                with psycopg.connect(self.path) as connection:
                    rows = connection.execute(
                        "SELECT payload FROM api_session_interactions WHERE session_id=%s ORDER BY created_at",
                        (session_id,),
                    ).fetchall()
                return [row[0] for row in rows]
            if self._connection:
                rows = self._connection.execute(
                    "SELECT payload FROM interactions WHERE session_id=? ORDER BY created_at", (session_id,)
                ).fetchall()
                return [json.loads(row[0]) for row in rows]
            return list(self._memory.get(session_id, []))

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if self._postgres:
                import psycopg  # type: ignore[import-not-found]
                with psycopg.connect(self.path) as connection:
                    cursor = connection.execute(
                        "DELETE FROM api_session_interactions WHERE session_id=%s", (session_id,)
                    )
                return cursor.rowcount > 0
            if self._connection:
                cursor = self._connection.execute("DELETE FROM interactions WHERE session_id=?", (session_id,))
                self._connection.commit()
                return cursor.rowcount > 0
            return self._memory.pop(session_id, None) is not None

    def close(self) -> None:
        if self._connection:
            self._connection.close()

    def ready(self) -> tuple[bool, str]:
        try:
            if self._postgres:
                import psycopg  # type: ignore[import-not-found]
                with psycopg.connect(self.path, connect_timeout=2) as connection:
                    connection.execute("SELECT 1").fetchone()
                return True, "postgres reachable"
            if self._connection is None:
                return True, "memory (test-only)"
            self._connection.execute("SELECT 1").fetchone()
            return True, "sqlite reachable"
        except Exception:
            return False, "session persistence unavailable"
