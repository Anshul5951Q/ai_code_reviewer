from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.base import Base

logger = logging.getLogger("ai_code_reviewer.db")

# Create async engine with pre-ping connection liveness verification
engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    echo=False,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_session_maker() -> async_sessionmaker:
    """Return the current async sessionmaker factory."""
    return async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an isolated async database session.

    Ensures clean commit on successful completion, automatic rollback on
    unhandled exceptions, and guaranteed session closure.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and verify connection."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as exc:
        logger.warning(f"Database initialization deferred or failed: {exc}")


async def close_db() -> None:
    """Gracefully dispose database connection pool on shutdown."""
    logger.info("Disposing database connection pool...")
    await engine.dispose()
    logger.info("Database connection pool disposed")
