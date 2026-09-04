"""
Tests for Phase 5 — M15 Candle Manager.
Covers:
  - New candle processing
  - Unfinished candle detection and rejection
  - Completed candle detection (10:00 candle completed only >= 10:15)
  - Duplicate candle prevention (timestamp <= last_processed_candle_time)
  - Out-of-order candle rejection
  - Backend restart scenario (state persistence and recovery from DB)
  - UTC handling and timezone conversion
  - M15 aggregation from smaller sub-period candles (M1/M5)
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.crud.candle import count_candles
from app.market.candle_manager import M15CandleManager
from app.market.models import NormalizedCandle
from app.market.xauusd_provider import MockXAUUSDProvider


@pytest.fixture
async def db_session():
    """Provides an isolated in-memory SQLite DB session for restart tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


# ─── 1. New Candle Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_completed_candle_processing():
    """A new completed candle is accepted, stored, and updates last_processed_candle_time."""
    manager = M15CandleManager(symbol="XAUUSD")

    # 10:00 -> 10:15 candle evaluated at 10:15:05 UTC
    candle_ts = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    eval_time = datetime(2026, 9, 4, 10, 15, 5, tzinfo=timezone.utc)

    candle = NormalizedCandle.create(
        timestamp=candle_ts,
        open=2480.0,
        high=2485.0,
        low=2478.0,
        close=2483.5,
        volume=250.0,
        timeframe="M15",
    )

    result = await manager.process_candle(candle, current_time=eval_time)
    assert result is not None
    assert result.timestamp == candle_ts
    assert result.close == 2483.5
    assert manager.last_processed_candle_time == candle_ts
    assert len(manager.candles) == 1


# ─── 2. Unfinished Candle Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unfinished_candle_rejected():
    """
    CRITICAL RULE:
    For a 10:00 -> 10:15 candle, evaluating it at 10:14:59 must be rejected.
    It is unfinished and must NOT be processed for signals.
    """
    manager = M15CandleManager(symbol="XAUUSD")

    candle_ts = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    # 1 second before candle closes
    eval_time = datetime(2026, 9, 4, 10, 14, 59, tzinfo=timezone.utc)

    candle = NormalizedCandle.create(
        timestamp=candle_ts,
        open=2480.0,
        high=2485.0,
        low=2478.0,
        close=2483.5,
    )

    assert manager.is_candle_completed(candle, current_time=eval_time) is False

    result = await manager.process_candle(candle, current_time=eval_time)
    assert result is None
    assert manager.last_processed_candle_time is None
    assert len(manager.candles) == 0


# ─── 3. Completed Candle Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_completed_candle_at_exact_close_time():
    """
    For a 10:00 -> 10:15 candle:
    At 10:15:00.000 UTC exactly, the candle is completed.
    """
    manager = M15CandleManager(symbol="XAUUSD")

    candle_ts = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    exact_close = datetime(2026, 9, 4, 10, 15, 0, tzinfo=timezone.utc)

    candle = NormalizedCandle.create(
        timestamp=candle_ts,
        open=2480.0,
        high=2485.0,
        low=2478.0,
        close=2483.5,
    )

    assert manager.is_candle_completed(candle, current_time=exact_close) is True
    result = await manager.process_candle(candle, current_time=exact_close)
    assert result is not None
    assert result.timestamp == candle_ts

    # Latest completed candle
    latest = manager.get_latest_completed_candle(current_time=exact_close)
    assert latest is not None
    assert latest.timestamp == candle_ts


# ─── 4. Duplicate Candle Prevention ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_candle_prevented():
    """
    Feeding the same candle twice must be rejected on the second call.
    Do not process candle_time <= last_processed_candle_time.
    """
    manager = M15CandleManager(symbol="XAUUSD")

    candle_ts = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    eval_time = datetime(2026, 9, 4, 10, 15, 1, tzinfo=timezone.utc)

    candle = NormalizedCandle.create(
        timestamp=candle_ts,
        open=2480.0,
        high=2485.0,
        low=2478.0,
        close=2483.5,
    )

    # First attempt: accepted
    r1 = await manager.process_candle(candle, current_time=eval_time)
    assert r1 is not None
    assert manager.last_processed_candle_time == candle_ts

    # Second attempt with identical timestamp: rejected as duplicate
    r2 = await manager.process_candle(candle, current_time=eval_time)
    assert r2 is None
    assert len(manager.candles) == 1

    # An older candle (e.g. 09:45) is also rejected because 09:45 <= 10:00
    older_candle = NormalizedCandle.create(
        timestamp=datetime(2026, 9, 4, 9, 45, tzinfo=timezone.utc),
        open=2475.0,
        high=2480.0,
        low=2474.0,
        close=2479.0,
    )
    r3 = await manager.process_candle(older_candle, current_time=eval_time)
    assert r3 is None


# ─── 5. Out-of-Order Candle Handling ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_out_of_order_candle_handling():
    """Candles arriving out of chronological order are rejected."""
    manager = M15CandleManager(symbol="XAUUSD")

    t1 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)

    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

    # Process t1 then t3
    c1 = NormalizedCandle.create(timestamp=t1, open=2480, high=2485, low=2478, close=2483)
    c3 = NormalizedCandle.create(timestamp=t3, open=2484, high=2488, low=2482, close=2486)

    await manager.process_candle(c1, current_time=now)
    await manager.process_candle(c3, current_time=now)
    assert manager.last_processed_candle_time == t3

    # Now t2 arrives late (out of order, t2 < t3)
    c2 = NormalizedCandle.create(timestamp=t2, open=2483, high=2486, low=2481, close=2484)
    res = await manager.process_candle(c2, current_time=now)
    assert res is None  # rejected due to timestamp <= last_processed_candle_time


# ─── 6. Backend Restart Scenario ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restart_scenario_recovers_state_and_avoids_duplicates(db_session: AsyncSession):
    """
    Persistence & Restart:
    1. Manager 1 processes candles and persists them to SQLite.
    2. Manager 1 shuts down.
    3. Manager 2 starts up, initializes from DB.
    4. Manager 2 restores last_processed_candle_time and in-memory cache.
    5. Re-sending previously processed candle is rejected.
    6. Sending new completed candle is accepted.
    """
    t1 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    now = datetime(2026, 9, 4, 11, 0, tzinfo=timezone.utc)

    c1 = NormalizedCandle.create(timestamp=t1, open=2480, high=2485, low=2478, close=2483)
    c2 = NormalizedCandle.create(timestamp=t2, open=2483, high=2488, low=2481, close=2487)

    # Instance 1: Run and persist
    manager1 = M15CandleManager(symbol="XAUUSD")
    await manager1.process_candle(c1, current_time=now, session=db_session)
    await manager1.process_candle(c2, current_time=now, session=db_session)

    assert manager1.last_processed_candle_time == t2
    assert await count_candles(db_session, "XAUUSD", "M15") == 2

    # Simulate restart: New instance created
    manager2 = M15CandleManager(symbol="XAUUSD")
    assert manager2.last_processed_candle_time is None
    assert len(manager2.candles) == 0

    # Initialize from DB
    await manager2.initialize_from_db(db_session)

    # State should be completely restored
    assert manager2.last_processed_candle_time == t2
    assert len(manager2.candles) == 2
    assert manager2.candles[-1].timestamp == t2

    # Attempt to re-process c2 (which was processed before restart)
    dup_res = await manager2.process_candle(c2, current_time=now, session=db_session)
    assert dup_res is None  # Duplicate rejected!

    # Process next new completed candle (10:30)
    t3 = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)
    c3 = NormalizedCandle.create(timestamp=t3, open=2487, high=2492, low=2485, close=2490)
    new_res = await manager2.process_candle(c3, current_time=now, session=db_session)
    assert new_res is not None
    assert manager2.last_processed_candle_time == t3
    assert await count_candles(db_session, "XAUUSD", "M15") == 3


# ─── 7. UTC Handling ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_utc_handling_with_timezone_offset_and_naive():
    """
    Verify timestamps from different timezones or naive datetimes
    are normalized to UTC and aligned to M15 boundaries correctly.
    """
    # Timezone offset: UTC+3 (e.g. 13:07:30 UTC+3 = 10:07:30 UTC -> aligns to 10:00:00 UTC)
    tz_plus_3 = timezone(timedelta(hours=3))
    t_offset = datetime(2026, 9, 4, 13, 7, 30, tzinfo=tz_plus_3)

    c = NormalizedCandle.create(
        timestamp=t_offset,
        open=2480,
        high=2485,
        low=2478,
        close=2483,
        timeframe="M15",
    )
    assert c.timestamp == datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert c.timestamp.tzinfo == timezone.utc

    # Naive datetime: assumed to be UTC
    t_naive = datetime(2026, 9, 4, 10, 22, 15)
    c_naive = NormalizedCandle.create(
        timestamp=t_naive,
        open=2480,
        high=2485,
        low=2478,
        close=2483,
        timeframe="M15",
    )
    assert c_naive.timestamp == datetime(2026, 9, 4, 10, 15, 0, tzinfo=timezone.utc)
    assert c_naive.timestamp.tzinfo == timezone.utc


# ─── 8. M15 Construction from Smaller Candles ─────────────────────────────────

def test_construct_m15_from_smaller_candles():
    """
    Test constructing standard M15 candles from smaller M5 bars.
    Three 5-minute bars in [10:00, 10:15) should aggregate into one M15 bar:
      - open = first open (2480.0)
      - high = max of all highs (2488.0)
      - low = min of all lows (2478.0)
      - close = last close (2485.5)
      - volume = sum of volumes (100 + 150 + 200 = 450)
    """
    m5_bars = [
        NormalizedCandle.create(
            timestamp=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
            open=2480.0,
            high=2484.0,
            low=2479.0,
            close=2482.0,
            volume=100.0,
            timeframe="M5",
        ),
        NormalizedCandle.create(
            timestamp=datetime(2026, 9, 4, 10, 5, tzinfo=timezone.utc),
            open=2482.0,
            high=2488.0,
            low=2481.0,
            close=2487.0,
            volume=150.0,
            timeframe="M5",
        ),
        NormalizedCandle.create(
            timestamp=datetime(2026, 9, 4, 10, 10, tzinfo=timezone.utc),
            open=2487.0,
            high=2487.5,
            low=2478.0,
            close=2485.5,
            volume=200.0,
            timeframe="M5",
        ),
    ]

    m15_list = M15CandleManager.construct_m15_from_smaller_candles(m5_bars)
    assert len(m15_list) == 1

    bar = m15_list[0]
    assert bar.timestamp == datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    assert bar.open == 2480.0
    assert bar.high == 2488.0
    assert bar.low == 2478.0
    assert bar.close == 2485.5
    assert bar.volume == 450.0


# ─── 9. Sync from Provider Integration ────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_from_provider_processes_completed_bars(db_session: AsyncSession):
    """Test full integration with provider: fetch, filter completed, save to DB."""
    t1 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)

    # Mock provider has 3 candles: 10:00, 10:15, 10:30
    candles = [
        NormalizedCandle.create(timestamp=t1, open=2480, high=2485, low=2478, close=2483),
        NormalizedCandle.create(timestamp=t2, open=2483, high=2488, low=2481, close=2486),
        NormalizedCandle.create(timestamp=t3, open=2486, high=2490, low=2484, close=2488),
    ]
    mock_provider = MockXAUUSDProvider(candle_data=candles)
    manager = M15CandleManager(symbol="XAUUSD", provider=mock_provider)

    # Current time is 10:35 UTC:
    # 10:00 is completed (closed at 10:15)
    # 10:15 is completed (closed at 10:30)
    # 10:30 is UNFINISHED (closes at 10:45)
    current_time = datetime(2026, 9, 4, 10, 35, tzinfo=timezone.utc)

    completed = await manager.sync_from_provider(
        session=db_session,
        limit=10,
        current_time=current_time,
    )

    # Only the first 2 completed candles should be returned
    assert len(completed) == 2
    assert completed[0].timestamp == t1
    assert completed[1].timestamp == t2
    assert manager.last_processed_candle_time == t2

    # Database has 2 saved candles
    assert await count_candles(db_session, "XAUUSD", "M15") == 2
