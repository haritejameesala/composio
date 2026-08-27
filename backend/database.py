"""
Async SQLAlchemy database setup.
The engine and session factory are created once; `Base` holds all ORM metadata.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Create the async engine.  echo=False in prod; set True temporarily to debug SQL.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    # SQLite-specific: allow the connection to be used from multiple asyncio tasks.
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# Session factory — used as a dependency in every request handler.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def create_tables() -> None:
    """Create all tables defined on Base.metadata (run once at startup)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
