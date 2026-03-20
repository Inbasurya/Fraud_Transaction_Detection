"""Async SQLAlchemy setup — supports PostgreSQL (Render) and SQLite (local dev)."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import settings

DATABASE_URL = settings.DATABASE_URL

# Normalize Render's postgres:// -> postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("sqlite:///"):
    # Local dev: use aiosqlite for async support
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite doesn't support pool_size or max_overflow
_engine_kwargs = dict(
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,     # Required for Render — detects stale connections
    pool_recycle=300,        # Recycle connections every 5 min
)
if _is_sqlite:
    # SQLite uses StaticPool — remove unsupported pool args
    _engine_kwargs.pop("pool_pre_ping")
    _engine_kwargs.pop("pool_recycle")
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
