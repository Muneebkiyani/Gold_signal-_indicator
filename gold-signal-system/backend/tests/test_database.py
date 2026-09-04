"""
Tests for Phase 3 — Database Layer.
Covers:
  - Models: Candle, Signal, SignalType, SignalSource
  - Duplicate protection via unique constraints
  - CRUD operations for Candle and Signal
  - Telegram alert tracking fields
  - Database initialization and session handling
  - PostgreSQL compatibility considerations
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.models.candle import Candle
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.crud.candle import (
    count_candles,
    create_candle,
    delete_candles,
    get_candle,
    get_candle_by_time,
    get_candles,
    get_latest_candle,
    save_candles,
)
from app.crud.signal import (
    DuplicateSignalError,
    count_signals,
    create_signal,
    get_pending_telegram_signals,
    get_signal,
    get_signal_by_bar,
    get_signals,
    update_telegram_status,
)


@pytest.fixture
async def db_session():
    """Provides a fresh isolated in-memory SQLite database session for each test."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


# ─── Model Tests ─────────────────────────────────────────────────────────────

def test_signal_type_enum():
    """Verify all required signal types exist with exact values."""
    assert SignalType.WAIT == "WAIT"
    assert SignalType.BUY == "BUY"
    assert SignalType.SELL == "SELL"
    assert SignalType.NO_ENTRY == "NO_ENTRY"
    assert set(s.value for s in SignalType) == {"WAIT", "BUY", "SELL", "NO_ENTRY"}


def test_signal_source_enum():
    """Verify all required signal sources exist."""
    assert SignalSource.EMA_RSI_ADX == "EMA_RSI_ADX"
    assert SignalSource.SMA_81 == "SMA_81"


def test_candle_model_creation():
    """Candle model instantiates correctly with all required fields."""
    now = datetime.now(timezone.utc)
    candle = Candle(
        symbol="XAUUSD",
        timeframe="M15",
        timestamp=now,
        open=2350.50,
        high=2355.80,
        low=2348.20,
        close=2354.10,
        volume=1420.0,
    )
    assert candle.symbol == "XAUUSD"
    assert candle.timeframe == "M15"
    assert candle.timestamp == now
    assert candle.open == 2350.50
    assert candle.high == 2355.80
    assert candle.low == 2348.20
    assert candle.close == 2354.10
    assert candle.volume == 1420.0
    assert candle.created_at is not None


def test_signal_model_creation():
    """Signal model instantiates with full indicator snapshot and Telegram defaults."""
    now = datetime.now(timezone.utc)
    signal = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=now,
        price=2354.10,
        ema_fast=2351.0,
        ema_slow=2345.0,
        rsi=58.5,
        adx=27.4,
        di_plus=31.2,
        di_minus=14.8,
        sma_81=2330.0,
        atr=4.5,
        trend="UP",
    )
    assert signal.signal_type == "BUY"
    assert signal.signal_source == "EMA_RSI_ADX"
    assert signal.telegram_sent is False
    assert signal.telegram_attempts == 0
    assert signal.telegram_last_attempt is None
    assert signal.telegram_error is None
    assert signal.created_at is not None


# ─── Candle CRUD Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_candle(db_session: AsyncSession):
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    candle = Candle(
        symbol="XAUUSD",
        timeframe="M15",
        timestamp=now,
        open=2350.0,
        high=2360.0,
        low=2345.0,
        close=2358.0,
        volume=100.0,
    )
    created = await create_candle(db_session, candle)
    assert created.id is not None

    fetched = await get_candle(db_session, created.id)
    assert fetched is not None
    assert fetched.symbol == "XAUUSD"
    assert fetched.close == 2358.0

    by_time = await get_candle_by_time(db_session, "XAUUSD", "M15", now)
    assert by_time is not None
    assert by_time.id == created.id


@pytest.mark.asyncio
async def test_get_candles_filtering_and_order(db_session: AsyncSession):
    base = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    for i in range(5):
        c = Candle(
            symbol="XAUUSD",
            timeframe="M15",
            timestamp=base + timedelta(minutes=i * 15),
            open=2350.0 + i,
            high=2355.0 + i,
            low=2348.0 + i,
            close=2352.0 + i,
            volume=50.0,
        )
        await create_candle(db_session, c)

    # Chronological ascending
    candles_asc = await get_candles(db_session, "XAUUSD", "M15", limit=3, ascending=True)
    assert len(candles_asc) == 3
    assert candles_asc[0].timestamp < candles_asc[1].timestamp

    # Descending (newest first)
    candles_desc = await get_candles(db_session, "XAUUSD", "M15", limit=2, ascending=False)
    assert len(candles_desc) == 2
    assert candles_desc[0].timestamp > candles_desc[1].timestamp

    # Latest candle
    latest = await get_latest_candle(db_session, "XAUUSD", "M15")
    assert latest is not None
    assert latest.timestamp.replace(tzinfo=timezone.utc) == datetime(2026, 9, 4, 11, 0, tzinfo=timezone.utc)

    # Count
    total = await count_candles(db_session, "XAUUSD", "M15")
    assert total == 5


@pytest.mark.asyncio
async def test_save_candles_batch_deduplication(db_session: AsyncSession):
    t1 = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 12, 15, tzinfo=timezone.utc)

    batch1 = [
        Candle(symbol="XAUUSD", timeframe="M15", timestamp=t1, open=2350, high=2355, low=2348, close=2352),
        Candle(symbol="XAUUSD", timeframe="M15", timestamp=t2, open=2352, high=2358, low=2350, close=2356),
    ]
    saved1 = await save_candles(db_session, batch1)
    assert len(saved1) == 2

    # Save same batch again - duplicates are skipped
    saved2 = await save_candles(db_session, batch1)
    assert len(saved2) == 0

    total = await count_candles(db_session, "XAUUSD", "M15")
    assert total == 2


@pytest.mark.asyncio
async def test_delete_candles(db_session: AsyncSession):
    t = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    await create_candle(
        db_session,
        Candle(symbol="XAUUSD", timeframe="M15", timestamp=t, open=2350, high=2355, low=2348, close=2352),
    )
    deleted = await delete_candles(db_session, "XAUUSD", "M15")
    assert deleted == 1
    assert await count_candles(db_session, "XAUUSD", "M15") == 0


# ─── Signal CRUD Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_signal(db_session: AsyncSession):
    now = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    signal = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=now,
        price=2360.50,
        ema_fast=2358.0,
        ema_slow=2352.0,
        rsi=62.0,
        adx=25.0,
        di_plus=28.0,
        di_minus=15.0,
        sma_81=2340.0,
        atr=3.8,
        trend="UP",
    )
    created = await create_signal(db_session, signal)
    assert created.id is not None

    fetched = await get_signal(db_session, created.id)
    assert fetched is not None
    assert fetched.signal_type == "BUY"
    assert fetched.price == 2360.50

    by_bar = await get_signal_by_bar(
        db_session, "XAUUSD", "M15", now, SignalSource.EMA_RSI_ADX, SignalType.BUY
    )
    assert by_bar is not None
    assert by_bar.id == created.id


@pytest.mark.asyncio
async def test_duplicate_signal_protection_raises(db_session: AsyncSession):
    """
    Ensure the unique constraint prevents inserting the same:
    (symbol, timeframe, candle_time, signal_source, signal_type)
    """
    now = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    sig1 = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=now,
        price=2360.50,
    )
    await create_signal(db_session, sig1)

    # Identical unique key
    sig2 = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=now,
        price=2365.00,
    )

    with pytest.raises(DuplicateSignalError):
        await create_signal(db_session, sig2, ignore_duplicates=False)

    assert await count_signals(db_session, "XAUUSD", "M15") == 1


@pytest.mark.asyncio
async def test_duplicate_signal_protection_ignore(db_session: AsyncSession):
    """When ignore_duplicates=True, returning the existing record instead of raising."""
    now = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    sig1 = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.SELL,
        signal_source=SignalSource.SMA_81,
        candle_time=now,
        price=2340.00,
    )
    created1 = await create_signal(db_session, sig1)

    sig2 = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.SELL,
        signal_source=SignalSource.SMA_81,
        candle_time=now,
        price=2340.00,
    )
    returned = await create_signal(db_session, sig2, ignore_duplicates=True)
    assert returned.id == created1.id
    assert await count_signals(db_session, "XAUUSD", "M15") == 1


@pytest.mark.asyncio
async def test_signals_different_type_or_source_allowed(db_session: AsyncSession):
    """Signals for the same bar but different source or type should succeed."""
    now = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    sig_ema = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=now,
        price=2360.00,
    )
    sig_sma = Signal(
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.SMA_81,
        candle_time=now,
        price=2360.00,
    )
    await create_signal(db_session, sig_ema)
    await create_signal(db_session, sig_sma)

    count = await count_signals(db_session, "XAUUSD", "M15")
    assert count == 2


@pytest.mark.asyncio
async def test_telegram_status_tracking(db_session: AsyncSession):
    now = datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc)
    sig = await create_signal(
        db_session,
        Signal(
            symbol="XAUUSD",
            timeframe="M15",
            signal_type=SignalType.BUY,
            signal_source=SignalSource.EMA_RSI_ADX,
            candle_time=now,
            price=2365.0,
        ),
    )

    # Initial state: pending
    pending = await get_pending_telegram_signals(db_session, max_attempts=3)
    assert len(pending) == 1
    assert pending[0].id == sig.id

    # Simulate failed dispatch
    updated_fail = await update_telegram_status(
        db_session, sig.id, sent=False, error="Telegram API timeout"
    )
    assert updated_fail.telegram_sent is False
    assert updated_fail.telegram_attempts == 1
    assert updated_fail.telegram_error == "Telegram API timeout"
    assert updated_fail.telegram_last_attempt is not None

    # Still pending because attempts (1) < max_attempts (3)
    pending_after_one_fail = await get_pending_telegram_signals(db_session, max_attempts=3)
    assert len(pending_after_one_fail) == 1

    # Simulate success
    updated_ok = await update_telegram_status(db_session, sig.id, sent=True)
    assert updated_ok.telegram_sent is True
    assert updated_ok.telegram_attempts == 2

    # No longer pending
    pending_now = await get_pending_telegram_signals(db_session, max_attempts=3)
    assert len(pending_now) == 0


@pytest.mark.asyncio
async def test_get_signals_filtering(db_session: AsyncSession):
    now = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)
    types = [SignalType.BUY, SignalType.SELL, SignalType.WAIT, SignalType.NO_ENTRY]
    for i, st in enumerate(types):
        t = now + timedelta(minutes=i * 15)
        await create_signal(
            db_session,
            Signal(
                symbol="XAUUSD",
                timeframe="M15",
                signal_type=st,
                signal_source=SignalSource.EMA_RSI_ADX,
                candle_time=t,
                price=2350.0 + i,
            ),
        )

    all_signals = await get_signals(db_session, limit=10)
    assert len(all_signals) == 4
    # Ordered newest first
    assert all_signals[0].candle_time > all_signals[1].candle_time

    buys = await get_signals(db_session, signal_type=SignalType.BUY)
    assert len(buys) == 1
    assert buys[0].signal_type == "BUY"

    no_entries = await get_signals(db_session, signal_type=SignalType.NO_ENTRY)
    assert len(no_entries) == 1
    assert no_entries[0].signal_type == "NO_ENTRY"

    assert await count_signals(db_session, signal_type="SELL") == 1
