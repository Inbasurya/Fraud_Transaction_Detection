"""Database engine and session factories.

Supports both async (asyncpg) and sync (psycopg2) PostgreSQL drivers.
Falls back to SQLite when DATABASE_URL points at a sqlite:// URI.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Sync engine (used by legacy code, Alembic, health checks) ────────────

_sync_url = settings.DATABASE_URL_SYNC or settings.POSTGRES_URI or settings.DATABASE_URL

_connect_args: dict = {}
if _sync_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    _sync_url,
    echo=False,
    connect_args=_connect_args,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
)

# SQLite-specific pragmas
if _sync_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a sync DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database connection check failed: %s", exc)
        return False
