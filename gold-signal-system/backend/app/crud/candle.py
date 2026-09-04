"""
CRUD operations for Candle model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Candle


async def create_candle(session: AsyncSession, candle: Candle) -> Candle:
    """Insert a new candle into the database."""
    session.add(candle)
    await session.commit()
    await session.refresh(candle)
    return candle


async def get_candle(session: AsyncSession, candle_id: int) -> Optional[Candle]:
    """Retrieve a single candle by its primary key ID."""
    statement = select(Candle).where(Candle.id == candle_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_candle_by_time(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    timestamp: datetime,
) -> Optional[Candle]:
    """Retrieve a candle for a given symbol, timeframe, and timestamp."""
    statement = select(Candle).where(
        Candle.symbol == symbol,
        Candle.timeframe == timeframe,
        Candle.timestamp == timestamp,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_candles(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    ascending: bool = True,
) -> Sequence[Candle]:
    """
    Query candles with optional date range, ordering, and limit.
    Default ordering is chronological (ascending).
    """
    statement = select(Candle).where(
        Candle.symbol == symbol,
        Candle.timeframe == timeframe,
    )

    if start_time is not None:
        statement = statement.where(Candle.timestamp >= start_time)
    if end_time is not None:
        statement = statement.where(Candle.timestamp <= end_time)

    if ascending:
        statement = statement.order_by(Candle.timestamp.asc())
    else:
        statement = statement.order_by(Candle.timestamp.desc())

    statement = statement.limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()


async def get_latest_candle(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
) -> Optional[Candle]:
    """Retrieve the latest candle by timestamp for a given symbol and timeframe."""
    statement = (
        select(Candle)
        .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
        .order_by(Candle.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def save_candles(
    session: AsyncSession,
    candles: list[Candle],
) -> list[Candle]:
    """
    Save a batch of candles, skipping duplicates based on (symbol, timeframe, timestamp).
    Works with both SQLite and standard databases.
    """
    saved = []
    for candle in candles:
        existing = await get_candle_by_time(
            session, candle.symbol, candle.timeframe, candle.timestamp
        )
        if existing is None:
            session.add(candle)
            saved.append(candle)
    if saved:
        await session.commit()
        for candle in saved:
            await session.refresh(candle)
    return saved


async def count_candles(
    session: AsyncSession,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> int:
    """Return total number of candles matching the filters."""
    statement = select(func.count(Candle.id))
    if symbol:
        statement = statement.where(Candle.symbol == symbol)
    if timeframe:
        statement = statement.where(Candle.timeframe == timeframe)
    result = await session.execute(statement)
    return result.scalar_one() or 0


async def delete_candles(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
) -> int:
    """Delete all candles for a given symbol and timeframe. Useful for resets/testing."""
    statement = select(Candle).where(
        Candle.symbol == symbol,
        Candle.timeframe == timeframe,
    )
    result = await session.execute(statement)
    candles = result.scalars().all()
    count = len(candles)
    for c in candles:
        await session.delete(c)
    await session.commit()
    return count
