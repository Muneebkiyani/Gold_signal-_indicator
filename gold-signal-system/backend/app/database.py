"""
XAUUSD Gold Signal System — Database Setup
Async SQLite for development, designed for smooth PostgreSQL migration.
SQLAlchemy + SQLModel.
"""

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import get_settings
# Import models to ensure they are registered with SQLModel.metadata
import app.models  # noqa: F401

settings = get_settings()

# ── Safe database connection setup ───────────────────────────────────────────
is_sqlite = settings.database_url.startswith("sqlite")

# Ensure the data directory exists if using local file-based SQLite
if is_sqlite:
    clean_path = (
        settings.database_url.replace("sqlite+aiosqlite:///", "")
        .replace("sqlite:///", "")
    )
    if clean_path and not clean_path.startswith(":memory:"):
        Path(clean_path).parent.mkdir(parents=True, exist_ok=True)

# SQLite requires check_same_thread=False for asyncio; PostgreSQL/asyncpg does not accept it
connect_args = {"check_same_thread": False} if is_sqlite else {}

# ── Async engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=connect_args,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Create all tables defined in SQLModel metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
