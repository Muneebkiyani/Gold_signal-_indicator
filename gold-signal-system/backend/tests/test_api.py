"""
Comprehensive test suite for Phase 11 — FastAPI API Layer.

Covers:
  - GET /api/health
  - GET /api/status
  - GET /api/market
  - GET /api/indicators (EMA9, EMA21, RSI, ADX, DI+, DI-, SMA81, ATR)
  - GET /api/signal
  - GET /api/signals (pagination, limit, offset, filters)
  - GET /api/signals/latest (404 and 200)
  - GET /api/settings (security checks: no API keys / Telegram tokens exposed)
  - PUT /api/settings (runtime updates and Pydantic validation)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.database import get_db
from app.main import app
from app.models.candle import Candle
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal


@pytest.fixture
async def api_client():
    """Configures test in-memory database and yields an AsyncClient for FastAPI."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def _override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, test_session_factory

    app.dependency_overrides.clear()
    await test_engine.dispose()


# ── Health Endpoint ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_health(api_client):
    client, _ = api_client
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    assert "uptime_seconds" in data


# ── Status Endpoint ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_status_default(api_client):
    client, _ = api_client
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_status"] in ("operational", "degraded")
    assert data["database_status"] == "connected"
    assert data["market_data_status"] in ("ready", "connected")
    assert data["telegram_status"] in ("disabled", "enabled", "misconfigured")
    assert data["signal_engine_status"] in ("idle", "running", "stopped")


# ── Market Endpoint ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_market_empty(api_client):
    client, _ = api_client
    resp = await client.get("/api/market")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "M15"
    assert data["price"] is None
    assert data["timestamp"] is None


@pytest.mark.asyncio
async def test_api_market_with_candle(api_client):
    client, session_factory = api_client
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)

    # Insert a candle into the database
    async with session_factory() as session:
        c = Candle(
            symbol="XAUUSD",
            timeframe="M15",
            timestamp=now,
            open=2500.0,
            high=2510.0,
            low=2495.0,
            close=2505.5,
            volume=120.0,
        )
        session.add(c)
        await session.commit()

    resp = await client.get("/api/market")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "M15"
    assert data["price"] == 2505.5
    assert "2026-09-04" in data["timestamp"]


# ── Indicators Endpoint ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_indicators_empty(api_client):
    client, _ = api_client
    resp = await client.get("/api/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert data["EMA9"] is None
    assert data["EMA21"] is None
    assert data["RSI"] is None
    assert data["ADX"] is None
    assert data["DI+"] is None
    assert data["DI-"] is None
    assert data["SMA81"] is None
    assert data["ATR"] is None


@pytest.mark.asyncio
async def test_api_indicators_calculated(api_client):
    client, session_factory = api_client
    base_time = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)

    # Insert 90 candles so all indicators (including SMA 81) can be calculated
    async with session_factory() as session:
        for i in range(90):
            price = 2500.0 + (i * 0.5)
            c = Candle(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp=base_time + timedelta(minutes=15 * i),
                open=price,
                high=price + 2.0,
                low=price - 2.0,
                close=price + 1.0,
                volume=100.0,
            )
            session.add(c)
        await session.commit()

    resp = await client.get("/api/indicators")
    assert resp.status_code == 200
    data = resp.json()

    # Check both uppercase and alias formats
    assert data["EMA9"] is not None
    assert data["EMA21"] is not None
    assert data["RSI"] is not None
    assert data["ADX"] is not None
    assert data["DI+"] is not None
    assert data["DI-"] is not None
    assert data["SMA81"] is not None
    assert data["ATR"] is not None
    assert data["ema_fast"] == data["EMA9"]
    assert data["ema_slow"] == data["EMA21"]


# ── Signals Endpoints ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_current_signal_empty(api_client):
    client, _ = api_client
    resp = await client.get("/api/signal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["signal"] == "WAIT"
    assert data["trend"] == "FLAT"


@pytest.mark.asyncio
async def test_api_current_signal_with_db_signal(api_client):
    client, session_factory = api_client
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        sig = Signal(
            symbol="XAUUSD",
            timeframe="M15",
            signal_type=SignalType.BUY.value,
            signal_source=SignalSource.EMA_RSI_ADX.value,
            candle_time=now,
            price=2515.5,
            trend="UP",
        )
        session.add(sig)
        await session.commit()

    resp = await client.get("/api/signal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["signal"] == "BUY"
    assert data["source"] == "EMA_RSI_ADX"
    assert data["price"] == 2515.5
    assert data["trend"] == "UP"


@pytest.mark.asyncio
async def test_api_signals_latest_404(api_client):
    client, _ = api_client
    resp = await client.get("/api/signals/latest")
    assert resp.status_code == 404
    assert "No signals found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_signals_latest_success(api_client):
    client, session_factory = api_client
    t1 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)

    async with session_factory() as session:
        sig1 = Signal(
            symbol="XAUUSD",
            timeframe="M15",
            signal_type=SignalType.BUY.value,
            signal_source=SignalSource.EMA_RSI_ADX.value,
            candle_time=t1,
            price=2500.0,
        )
        sig2 = Signal(
            symbol="XAUUSD",
            timeframe="M15",
            signal_type=SignalType.SELL.value,
            signal_source=SignalSource.SMA_81.value,
            candle_time=t2,
            price=2520.0,
        )
        session.add(sig1)
        session.add(sig2)
        await session.commit()

    resp = await client.get("/api/signals/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["signal_type"] == "SELL"
    assert data["signal_source"] == "SMA_81"
    assert data["price"] == 2520.0


@pytest.mark.asyncio
async def test_api_signals_pagination_and_filter(api_client):
    client, session_factory = api_client
    base = datetime(2026, 9, 4, 1, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        for i in range(10):
            st = SignalType.BUY.value if i % 2 == 0 else SignalType.SELL.value
            sig = Signal(
                symbol="XAUUSD",
                timeframe="M15",
                signal_type=st,
                signal_source=SignalSource.EMA_RSI_ADX.value,
                candle_time=base.replace(hour=i),
                price=2500.0 + i,
            )
            session.add(sig)
        await session.commit()

    # Pagination: limit=3, offset=0
    resp = await client.get("/api/signals?limit=3&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert len(data["items"]) == 3
    assert data["limit"] == 3
    assert data["offset"] == 0

    # Filter by signal_type=BUY
    resp_buy = await client.get("/api/signals?signal_type=BUY")
    assert resp_buy.status_code == 200
    data_buy = resp_buy.json()
    assert data_buy["total"] == 5
    for item in data_buy["items"]:
        assert item["signal_type"] == "BUY"


# ── Settings Endpoints (Security & Update) ────────────────────────────────────


@pytest.mark.asyncio
async def test_api_settings_security_masking(api_client):
    """Verify that private keys and Telegram tokens are strictly omitted."""
    client, _ = api_client
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()

    # Public settings should exist
    assert "symbol" in data
    assert "timeframe" in data
    assert "ema_fast" in data
    assert "ema_slow" in data
    assert "rsi_length" in data
    assert "poll_interval_seconds" in data

    # STRICT SECURITY: Private credentials must NEVER be exposed
    assert "telegram_bot_token" not in data
    assert "telegram_chat_id" not in data
    assert "data_provider_api_key" not in data
    assert "data_provider_base_url" not in data
    assert "database_url" not in data


@pytest.mark.asyncio
async def test_api_put_settings_valid(api_client):
    client, _ = api_client
    payload = {
        "poll_interval_seconds": 120,
        "ema_fast": 10,
        "ema_slow": 25,
    }
    resp = await client.put("/api/settings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["poll_interval_seconds"] == 120
    assert data["ema_fast"] == 10
    assert data["ema_slow"] == 25


@pytest.mark.asyncio
async def test_api_put_settings_validation_errors(api_client):
    client, _ = api_client

    # Case 1: ema_fast >= ema_slow
    resp = await client.put(
        "/api/settings",
        json={"ema_fast": 30, "ema_slow": 20},
    )
    assert resp.status_code == 422
    assert "EMA fast" in resp.json()["detail"]

    # Case 2: rsi_oversold >= rsi_overbought
    resp2 = await client.put(
        "/api/settings",
        json={"rsi_oversold": 50.0, "rsi_overbought": 50.0},
    )
    assert resp2.status_code == 422
    assert "RSI oversold" in resp2.json()["detail"]
