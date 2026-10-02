"""Memory, SQLite, and PostgreSQL checkpoint factories with DSN redaction."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3

from langgraph.checkpoint.memory import MemorySaver


def redact_dsn(value: str) -> str:
    return re.sub(r"(?<=://)([^:@/]+):([^@/]+)@", r"\1:***@", value)


class CheckpointStore:
    def __init__(self, *, mode: str = "memory", uri: str | None = None):
        self.mode = mode
        self.uri = uri
        self._resource = None
        self._connection = None
        if mode == "memory":
            self.saver = MemorySaver()
        elif mode == "sqlite":
            from langgraph.checkpoint.sqlite import SqliteSaver
            if not uri: raise ValueError("sqlite checkpoint mode requires a path")
            path = Path(uri).resolve(); path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(path, check_same_thread=False)
            self.saver = SqliteSaver(self._connection)
        elif mode == "postgres":
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
            if not uri: raise ValueError("postgres checkpoint mode requires a DSN")
            self._resource = ConnectionPool(
                conninfo=uri, min_size=1, max_size=4,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                check=ConnectionPool.check_connection, open=True,
            )
            self._resource.wait(timeout=10)
            self.saver = PostgresSaver(self._resource)
            self.saver.setup()
        else:
            raise ValueError("checkpoint mode must be memory, sqlite, or postgres")

    @classmethod
    def from_environment(cls) -> "CheckpointStore":
        mode = os.getenv("CHECKPOINT_BACKEND", "memory").lower()
        uri = os.getenv("CHECKPOINT_URI")
        return cls(mode=mode, uri=uri)

    def close(self) -> None:
        if self._resource is not None:
            self._resource.close()
        if self._connection is not None:
            self._connection.close()
