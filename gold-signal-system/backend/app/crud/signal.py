"""
CRUD operations for Signal model.
Includes duplicate protection handling according to the unique constraint:
(symbol, timeframe, candle_time, signal_source, signal_type).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence, Union

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal


class DuplicateSignalError(Exception):
    """Raised when attempting to insert a duplicate signal violating uq_signal_bar."""

    def __init__(self, message: str, signal: Signal) -> None:
        super().__init__(message)
        self.signal = signal


async def get_signal_by_bar(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    candle_time: datetime,
    signal_source: Union[str, SignalSource],
    signal_type: Union[str, SignalType],
) -> Optional[Signal]:
    """
    Look up a signal by its unique composite key:
    (symbol, timeframe, candle_time, signal_source, signal_type).
    """
    src_val = signal_source.value if isinstance(signal_source, SignalSource) else str(signal_source)
    type_val = signal_type.value if isinstance(signal_type, SignalType) else str(signal_type)

    statement = select(Signal).where(
        Signal.symbol == symbol,
        Signal.timeframe == timeframe,
        Signal.candle_time == candle_time,
        Signal.signal_source == src_val,
        Signal.signal_type == type_val,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def create_signal(
    session: AsyncSession,
    signal: Signal,
    ignore_duplicates: bool = False,
) -> Signal:
    """
    Create a new Signal row in the database.

    If a signal with the same (symbol, timeframe, candle_time, signal_source, signal_type)
    already exists:
      - If ignore_duplicates is True: returns the existing record without raising.
      - If ignore_duplicates is False: raises DuplicateSignalError.
    """
    session.add(signal)
    try:
        await session.commit()
        await session.refresh(signal)
        return signal
    except IntegrityError as exc:
        await session.rollback()
        existing = await get_signal_by_bar(
            session=session,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            candle_time=signal.candle_time,
            signal_source=signal.signal_source,
            signal_type=signal.signal_type,
        )
        if ignore_duplicates and existing is not None:
            return existing
        raise DuplicateSignalError(
            f"Duplicate signal rejected: {signal.symbol} {signal.timeframe} "
            f"at {signal.candle_time} ({signal.signal_source}/{signal.signal_type})",
            signal=signal,
        ) from exc


async def get_signal(session: AsyncSession, signal_id: int) -> Optional[Signal]:
    """Retrieve a single signal by its primary key ID."""
    statement = select(Signal).where(Signal.id == signal_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_signals(
    session: AsyncSession,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    signal_type: Optional[Union[str, SignalType]] = None,
    signal_source: Optional[Union[str, SignalSource]] = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Signal]:
    """
    Query signals ordered by candle_time descending (newest first).
    Supports filtering by symbol, timeframe, signal_type, and signal_source.
    """
    statement = select(Signal)

    if symbol:
        statement = statement.where(Signal.symbol == symbol)
    if timeframe:
        statement = statement.where(Signal.timeframe == timeframe)
    if signal_type:
        val = signal_type.value if isinstance(signal_type, SignalType) else str(signal_type)
        statement = statement.where(Signal.signal_type == val)
    if signal_source:
        val = signal_source.value if isinstance(signal_source, SignalSource) else str(signal_source)
        statement = statement.where(Signal.signal_source == val)

    statement = statement.order_by(Signal.candle_time.desc(), Signal.id.desc())
    statement = statement.limit(limit).offset(offset)

    result = await session.execute(statement)
    return result.scalars().all()


async def get_latest_signal(
    session: AsyncSession,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Optional[Signal]:
    """Retrieve the most recent signal by candle_time."""
    statement = select(Signal)
    if symbol:
        statement = statement.where(Signal.symbol == symbol)
    if timeframe:
        statement = statement.where(Signal.timeframe == timeframe)
    statement = statement.order_by(Signal.candle_time.desc(), Signal.id.desc()).limit(1)

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_telegram_status(
    session: AsyncSession,
    signal_id: int,
    sent: bool,
    error: Optional[str] = None,
) -> Optional[Signal]:
    """
    Update Telegram delivery status and attempt tracking for a signal.
    """
    signal = await get_signal(session, signal_id)
    if signal is None:
        return None

    signal.telegram_sent = sent
    signal.telegram_attempts += 1
    signal.telegram_last_attempt = datetime.now(timezone.utc)
    signal.telegram_error = error

    session.add(signal)
    await session.commit()
    await session.refresh(signal)
    return signal


async def get_pending_telegram_signals(
    session: AsyncSession,
    max_attempts: int = 3,
    limit: int = 50,
) -> Sequence[Signal]:
    """
    Retrieve signals that have not yet been sent via Telegram
    and have not exceeded max_attempts.
    """
    statement = (
        select(Signal)
        .where(
            Signal.telegram_sent == False,  # noqa: E712
            Signal.telegram_attempts < max_attempts,
        )
        .order_by(Signal.candle_time.asc())
        .limit(limit)
    )
    result = await session.execute(statement)
    return result.scalars().all()


async def count_signals(
    session: AsyncSession,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    signal_type: Optional[Union[str, SignalType]] = None,
) -> int:
    """Return total number of signals matching the criteria."""
    statement = select(func.count(Signal.id))
    if symbol:
        statement = statement.where(Signal.symbol == symbol)
    if timeframe:
        statement = statement.where(Signal.timeframe == timeframe)
    if signal_type:
        val = signal_type.value if isinstance(signal_type, SignalType) else str(signal_type)
        statement = statement.where(Signal.signal_type == val)

    result = await session.execute(statement)
    return result.scalar_one() or 0
