"""
Tests for Phase 8 — Unified Signal Engine.
Covers:
  - EMA BUY signal generation and DB storage
  - EMA SELL signal generation and DB storage
  - SMA BUY signal generation and DB storage
  - SMA SELL signal generation and DB storage
  - WAIT signal handling (not stored in DB)
  - NO ENTRY signal handling (stored on transition)
  - Multiple signals on the same candle (EMA BUY and SMA BUY coexistence)
  - Duplicate processing prevention
  - Backend restart recovery and state restoration
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.crud.signal import count_signals, get_signals
from app.market.models import NormalizedCandle
from app.models.enums import SignalType
from app.services.signal_engine import SignalEngine
from app.strategy.engine import IndicatorValues


# ─── Test Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
async def db_session():
    """Isolated in-memory SQLite database session."""
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


class MockIndicatorEngine:
    """Mock IndicatorEngine returning pre-set IndicatorValues for deterministic tests."""

    def __init__(self, series: list[IndicatorValues]) -> None:
        self.series = series

    def calculate_series(self, candles) -> list[IndicatorValues]:
        return self.series

    def calculate(self, candles) -> IndicatorValues:
        return self.series[-1]


def create_candles(n: int = 2, base_price: float = 2350.0) -> list[NormalizedCandle]:
    base_t = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    res = []
    for i in range(n):
        t = base_t + timedelta(minutes=i * 15)
        p = base_price + i * 2.0
        res.append(
            NormalizedCandle.create(
                timestamp=t,
                open=p,
                high=p + 3.0,
                low=p - 2.0,
                close=p + 1.0,
                volume=100.0,
                timeframe="M15",
            )
        )
    return res


# ─── 1. EMA BUY Test ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_ema_buy(db_session: AsyncSession):
    """EMA/RSI/ADX conditions met -> generates and persists EMA BUY signal."""
    candles = create_candles(2)
    eval_time = candles[-1].timestamp + timedelta(minutes=15, seconds=5)

    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]
    mock_ind = MockIndicatorEngine(series)
    engine = SignalEngine(indicator_engine=mock_ind)

    # Process first candle then second
    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "BUY"
    assert sig.signal_source == "EMA_RSI_ADX"
    assert sig.price == candles[1].close
    assert sig.trend == "UP"

    # Verify in DB
    db_sigs = await get_signals(db_session, signal_type=SignalType.BUY)
    assert len(db_sigs) == 1
    assert db_sigs[0].signal_source == "EMA_RSI_ADX"


# ─── 2. EMA SELL Test ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_ema_sell(db_session: AsyncSession):
    """EMA/RSI/ADX conditions met -> generates and persists EMA SELL signal."""
    candles = create_candles(2)
    eval_time = candles[-1].timestamp + timedelta(minutes=15, seconds=5)

    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=45.0, adx=25.0, di_plus=12.0, di_minus=25.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=40.0, adx=26.0, di_plus=10.0, di_minus=28.0),
    ]
    mock_ind = MockIndicatorEngine(series)
    engine = SignalEngine(indicator_engine=mock_ind)

    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "SELL"
    assert sig.signal_source == "EMA_RSI_ADX"
    assert sig.trend == "DOWN"


# ─── 3. SMA BUY Test ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_sma_buy(db_session: AsyncSession):
    """Price crosses above SMA 81 -> generates and persists SMA BUY signal."""
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    candles = [
        NormalizedCandle.create(timestamp=t0, open=2335, high=2340, low=2334, close=2338.0),
        NormalizedCandle.create(timestamp=t1, open=2338, high=2348, low=2337, close=2345.0),
    ]
    eval_time = t1 + timedelta(minutes=15, seconds=5)

    series = [
        # Prev close (2338) <= prev SMA (2340)
        IndicatorValues(
            ema_fast=2335.0, ema_slow=2336.0, rsi=52.0, adx=15.0,
            di_plus=15.0, di_minus=15.0, sma_81=2340.0,
        ),
        # Curr close (2345) > curr SMA (2341)
        IndicatorValues(
            ema_fast=2338.0, ema_slow=2339.0, rsi=55.0, adx=15.0,
            di_plus=16.0, di_minus=15.0, sma_81=2341.0,
        ),
    ]
    mock_ind = MockIndicatorEngine(series)
    engine = SignalEngine(indicator_engine=mock_ind)

    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "BUY"
    assert sig.signal_source == "SMA_81"
    assert sig.price == 2345.0


# ─── 4. SMA SELL Test ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_sma_sell(db_session: AsyncSession):
    """Price crosses below SMA 81 -> generates and persists SMA SELL signal."""
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    candles = [
        NormalizedCandle.create(timestamp=t0, open=2345, high=2348, low=2340, close=2342.0),
        NormalizedCandle.create(timestamp=t1, open=2342, high=2343, low=2334, close=2336.0),
    ]
    eval_time = t1 + timedelta(minutes=15, seconds=5)

    series = [
        IndicatorValues(ema_fast=2345.0, ema_slow=2344.0, rsi=48.0, adx=15.0, di_plus=15.0, di_minus=15.0, sma_81=2340.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2343.0, rsi=44.0, adx=15.0, di_plus=14.0, di_minus=16.0, sma_81=2339.0),
    ]
    mock_ind = MockIndicatorEngine(series)
    engine = SignalEngine(indicator_engine=mock_ind)

    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "SELL"
    assert sig.signal_source == "SMA_81"
    assert sig.price == 2336.0


# ─── 5. WAIT Handling Test ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_wait_not_stored(db_session: AsyncSession):
    """Normal bars without triggers produce WAIT states which are NOT stored in DB."""
    candles = create_candles(2)
    eval_time = candles[-1].timestamp + timedelta(minutes=15, seconds=5)

    series = [
        # Normal baseline with no crossovers
        IndicatorValues(ema_fast=2345.0, ema_slow=2340.0, rsi=55.0, adx=25.0, di_plus=20.0, di_minus=15.0, sma_81=2300.0),
        IndicatorValues(ema_fast=2347.0, ema_slow=2341.0, rsi=56.0, adx=25.0, di_plus=20.0, di_minus=15.0, sma_81=2300.0),
    ]
    engine = SignalEngine(indicator_engine=MockIndicatorEngine(series))

    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    # None stored because both produced WAIT and store_wait=False
    assert len(signals) == 0
    assert await count_signals(db_session, "XAUUSD", "M15") == 0


# ─── 6. NO ENTRY Test ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_no_entry_stored_on_transition(db_session: AsyncSession):
    """Transitioning into no-entry zone generates NO_ENTRY signal and saves to DB."""
    candles = create_candles(2)
    eval_time = candles[-1].timestamp + timedelta(minutes=15, seconds=5)

    series = [
        # Previous bar: normal zone (ADX=22 >= 20, RSI=55)
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=22.0, di_plus=20.0, di_minus=15.0),
        # Current bar: drops into weak trend (ADX=18 < 20)
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=18.0, di_plus=20.0, di_minus=15.0),
    ]
    engine = SignalEngine(indicator_engine=MockIndicatorEngine(series))

    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "NO_ENTRY"
    assert sig.signal_source == "EMA_RSI_ADX"

    # Persisted in DB
    db_sigs = await get_signals(db_session, signal_type=SignalType.NO_ENTRY)
    assert len(db_sigs) == 1


# ─── 7. Multiple Signals on Same Candle ───────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_multiple_signals_same_candle(db_session: AsyncSession):
    """
    CRITICAL RULE:
    EMA/RSI/ADX and SMA 81 are independent signal systems.
    If both trigger on the same candle, BOTH must be saved under their respective source.
    """
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    candles = [
        NormalizedCandle.create(timestamp=t0, open=2335, high=2342, low=2334, close=2338.0),
        NormalizedCandle.create(timestamp=t1, open=2338, high=2349, low=2337, close=2348.0),
    ]
    eval_time = t1 + timedelta(minutes=15, seconds=5)

    series = [
        # Prev: EMA fast <= slow; price <= SMA81
        IndicatorValues(
            ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0,
            di_plus=25.0, di_minus=15.0, sma_81=2340.0,
        ),
        # Curr: EMA fast > slow (BUY); price > SMA81 (BUY)
        IndicatorValues(
            ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0,
            di_plus=28.0, di_minus=12.0, sma_81=2341.0,
        ),
    ]
    engine = SignalEngine(indicator_engine=MockIndicatorEngine(series))

    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)
    signals = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)

    # Both signals produced!
    assert len(signals) == 2
    sources = {s.signal_source for s in signals}
    assert sources == {"EMA_RSI_ADX", "SMA_81"}
    for s in signals:
        assert s.signal_type == "BUY"

    # Both persisted in DB
    total_db = await count_signals(db_session, "XAUUSD", "M15")
    assert total_db == 2


# ─── 8. Duplicate Processing Prevention ───────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_duplicate_processing_prevented(db_session: AsyncSession):
    """
    Feeding the same completed candle repeatedly must NOT re-evaluate
    or generate duplicate signals in the database.
    """
    candles = create_candles(2)
    eval_time = candles[-1].timestamp + timedelta(minutes=15, seconds=5)

    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]
    engine = SignalEngine(indicator_engine=MockIndicatorEngine(series))

    # Feed first candle so history has >= 2 bars for crossover detection
    await engine.process_candle(candles[0], session=db_session, current_time=eval_time)

    # First pass of candle[1]: generates 1 signal
    sigs1 = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)
    assert len(sigs1) == 1
    assert await count_signals(db_session, "XAUUSD", "M15") == 1

    # Second pass of candle[1]: duplicate candle rejected
    sigs2 = await engine.process_candle(candles[1], session=db_session, current_time=eval_time)
    assert len(sigs2) == 0
    # Still only 1 signal in DB
    assert await count_signals(db_session, "XAUUSD", "M15") == 1


# ─── 9. Restart Recovery ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_engine_restart_recovery(db_session: AsyncSession):
    """
    Simulate backend shutdown and restart:
      1. Engine 1 processes candle and stores signal.
      2. Engine 1 terminates.
      3. Engine 2 starts, calls initialize(db_session).
      4. Engine 2 recovers state from DB.
      5. Re-sending previously processed candle is ignored.
      6. Sending next new candle generates next signal.
    """
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)

    c0 = NormalizedCandle.create(timestamp=t0, open=2335, high=2340, low=2334, close=2338.0)
    c1 = NormalizedCandle.create(timestamp=t1, open=2338, high=2348, low=2337, close=2345.0)
    c2 = NormalizedCandle.create(timestamp=t2, open=2345, high=2352, low=2344, close=2350.0)

    eval_time = t2 + timedelta(minutes=15, seconds=5)

    series1 = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]

    # Run Engine 1
    engine1 = SignalEngine(indicator_engine=MockIndicatorEngine(series1))
    await engine1.process_candle(c0, session=db_session, current_time=eval_time)
    sigs_eng1 = await engine1.process_candle(c1, session=db_session, current_time=eval_time)
    assert len(sigs_eng1) == 1
    assert await count_signals(db_session, "XAUUSD", "M15") == 1

    # Simulate Restart: Create fresh Engine 2
    engine2 = SignalEngine()
    assert engine2.last_evaluated_candle_time is None

    # Initialize from DB
    await engine2.initialize(db_session)
    assert engine2.last_evaluated_candle_time == t1

    # Re-sending c1 to Engine 2 -> duplicate rejected!
    res_c1 = await engine2.process_candle(c1, session=db_session, current_time=eval_time)
    assert len(res_c1) == 0

    # Sending new candle c2 to Engine 2 -> accepted & processed
    res_c2 = await engine2.process_candle(c2, session=db_session, current_time=eval_time)
    # Candle c2 is ingested and processed
    assert engine2.last_evaluated_candle_time == t2
