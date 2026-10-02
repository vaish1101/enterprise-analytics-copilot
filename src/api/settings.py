from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppSettings:
    app_mode: str = "development"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:8000")
    rate_limit_per_minute: int = 10
    max_question_length: int = 1000
    request_timeout_seconds: float = 90.0
    checkpoint_backend: str = "sqlite"
    checkpoint_uri: str = str(ROOT / "data/checkpoints/step8.sqlite")
    retrieval_backend: str = "local"
    database_url: str = ""
    session_db_path: str = str(ROOT / "data/checkpoints/step8-sessions.sqlite")
    log_level: str = "INFO"
    system_version: str = "step8-product-1.0.0"
    public_demo: bool = False

    def __post_init__(self):
        if self.public_demo and (self.app_mode != "demo" or self.retrieval_backend != "local"):
            raise ValueError("PUBLIC_DEMO requires APP_MODE=demo and RETRIEVAL_BACKEND=local")

    @classmethod
    def from_environment(cls) -> "AppSettings":
        origins = tuple(
            item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")
            if item.strip()
        )
        return cls(
            app_mode=os.getenv("APP_MODE", "development").lower(),
            public_demo=os.getenv("PUBLIC_DEMO", "0") == "1",
            cors_origins=origins,
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")),
            max_question_length=int(os.getenv("MAX_QUESTION_LENGTH", "1000")),
            request_timeout_seconds=float(os.getenv("APP_REQUEST_TIMEOUT_SECONDS", "90")),
            checkpoint_backend=os.getenv("CHECKPOINT_BACKEND", "sqlite").lower(),
            checkpoint_uri=os.getenv("CHECKPOINT_URI", str(ROOT / "data/checkpoints/step8.sqlite")),
            retrieval_backend=os.getenv("RETRIEVAL_BACKEND", "local").lower(),
            database_url=os.getenv("DATABASE_URL", ""),
            session_db_path=os.getenv(
                "SESSION_DATABASE_URL",
                os.getenv("SESSION_DB_PATH", str(ROOT / "data/checkpoints/step8-sessions.sqlite")),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    @property
    def is_demo(self) -> bool:
        return self.app_mode == "demo"

    @property
    def is_test(self) -> bool:
        return self.app_mode == "test"
