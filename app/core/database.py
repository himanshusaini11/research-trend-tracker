from collections.abc import AsyncGenerator

from sqlalchemy.engine import Engine
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.models import Base


# ---------------------------------------------------------------------------
# Async engine (used by the application at runtime)
# ---------------------------------------------------------------------------
async_engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Sync engine (used by Alembic migrations only — created lazily)
# ---------------------------------------------------------------------------
def get_sync_engine() -> Engine:
    """Return a sync psycopg2 engine. Called only from Alembic env.py, never at import time."""
    return create_engine(
        settings.postgres_dsn_sync,
        pool_pre_ping=True,
        echo=settings.debug,
    )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Dev helper
# ---------------------------------------------------------------------------
async def create_all() -> None:
    """Create all tables from metadata. Use only in dev/tests — prefer Alembic otherwise."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
