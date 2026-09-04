"""
Tests for Phase 4 — XAUUSD Market Data Layer.
Covers:
  - Valid responses (price, historical candles, latest candle)
  - Invalid responses (HTTP errors, API error payloads)
  - Network timeout
  - Missing candles / empty responses
  - Duplicate candles (deduplication)
  - Malformed data (missing keys, non-numeric values, bad timestamps)
  - Deterministic candle boundary alignment in UTC
  - MockXAUUSDProvider offline functionality
"""

from datetime import datetime, timezone
import pytest
import httpx

from app.market.base_provider import BaseMarketDataProvider
from app.market.models import (
    MalformedDataError,
    NormalizedCandle,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
    align_to_boundary,
    align_to_m15_boundary,
)
from app.market.xauusd_provider import (
    MockXAUUSDProvider,
    TwelveDataXAUUSDProvider,
    format_symbol_for_twelvedata,
    get_market_provider,
)


# ─── Helpers for Mocking HTTP Responses ────────────────────────────────────────

def make_mock_client(handler) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient backed by an in-memory handler function."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


# ─── Boundary and Normalization Tests ─────────────────────────────────────────

def test_m15_boundary_alignment():
    """Verify timestamps align deterministically to 0, 15, 30, 45 minute marks."""
    # 10:14:32 -> 10:00:00
    t1 = datetime(2026, 9, 4, 10, 14, 32)
    aligned1 = align_to_m15_boundary(t1)
    assert aligned1 == datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert aligned1.tzinfo == timezone.utc

    # 10:29:59 -> 10:15:00
    t2 = datetime(2026, 9, 4, 10, 29, 59)
    aligned2 = align_to_m15_boundary(t2)
    assert aligned2 == datetime(2026, 9, 4, 10, 15, 0, tzinfo=timezone.utc)

    # 10:45:00 -> 10:45:00
    t3 = datetime(2026, 9, 4, 10, 45, 0)
    aligned3 = align_to_m15_boundary(t3)
    assert aligned3 == datetime(2026, 9, 4, 10, 45, 0, tzinfo=timezone.utc)


def test_align_to_boundary_various_timeframes():
    """Test boundary alignment across M1, M5, M30, H1, D1."""
    t = datetime(2026, 9, 4, 10, 23, 45, tzinfo=timezone.utc)
    assert align_to_boundary(t, "M1") == datetime(2026, 9, 4, 10, 23, 0, tzinfo=timezone.utc)
    assert align_to_boundary(t, "M5") == datetime(2026, 9, 4, 10, 20, 0, tzinfo=timezone.utc)
    assert align_to_boundary(t, "M30") == datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert align_to_boundary(t, "H1") == datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert align_to_boundary(t, "D1") == datetime(2026, 9, 4, 0, 0, 0, tzinfo=timezone.utc)


def test_symbol_formatter():
    """Verify symbol normalization for Twelve Data."""
    assert format_symbol_for_twelvedata("XAUUSD") == "XAU/USD"
    assert format_symbol_for_twelvedata("xauusd") == "XAU/USD"
    assert format_symbol_for_twelvedata("XAU/USD") == "XAU/USD"
    assert format_symbol_for_twelvedata("EURUSD") == "EURUSD"


# ─── 1. Valid Response Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_price_response():
    """Test get_latest_price() with valid JSON."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "price" in str(request.url)
        assert "symbol=XAU%2FUSD" in str(request.url)
        return httpx.Response(200, json={"price": "2495.75000"})

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(api_key="test_key", client=client)
        price = await provider.get_latest_price("XAUUSD")
        assert price == 2495.75
        assert isinstance(price, float)


@pytest.mark.asyncio
async def test_valid_historical_candles_response():
    """Test get_historical_candles() returns chronologically sorted normalized candles."""
    raw_payload = {
        "meta": {"symbol": "XAU/USD", "interval": "15min"},
        "values": [
            # Twelve Data returns reverse chronological order (newest first)
            {
                "datetime": "2026-09-04 10:15:00",
                "open": "2492.00",
                "high": "2496.50",
                "low": "2490.10",
                "close": "2495.80",
                "volume": "350",
            },
            {
                "datetime": "2026-09-04 10:00:00",
                "open": "2488.50",
                "high": "2493.00",
                "low": "2487.20",
                "close": "2491.80",
                "volume": "420",
            },
        ],
        "status": "ok",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "time_series" in str(request.url)
        assert "interval=15min" in str(request.url)
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(api_key="test_key", client=client)
        candles = await provider.get_historical_candles("XAUUSD", "M15")

        assert len(candles) == 2
        # Verify chronological ascending order (oldest first)
        assert candles[0].timestamp < candles[1].timestamp
        assert candles[0].timestamp == datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
        assert candles[0].open == 2488.50
        assert candles[0].close == 2491.80
        assert candles[0].volume == 420.0

        assert candles[1].timestamp == datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
        assert candles[1].close == 2495.80


@pytest.mark.asyncio
async def test_valid_latest_candle_response():
    """Test get_latest_candle() returns the single most recent candle."""
    raw_payload = {
        "values": [
            {
                "datetime": "2026-09-04 10:15:00",
                "open": "2492.00",
                "high": "2496.50",
                "low": "2490.10",
                "close": "2495.80",
                "volume": "350",
            }
        ],
        "status": "ok",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(api_key="test_key", client=client)
        candle = await provider.get_latest_candle("XAUUSD", "M15")
        assert candle is not None
        assert candle.timestamp == datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)
        assert candle.close == 2495.80


# ─── 2. Invalid Response Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_http_error_response():
    """Test handling of HTTP error status code (e.g. 401 Unauthorized)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized: invalid apikey")

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(ProviderResponseError) as exc_info:
            await provider.get_latest_price("XAUUSD")
        assert exc_info.value.status_code == 401
        assert "401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_api_json_error_response():
    """Test handling of Twelve Data JSON error format returned with HTTP 200/400."""
    error_payload = {
        "status": "error",
        "code": 400,
        "message": "Symbol 'UNKNOWN' not found",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=error_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(ProviderResponseError) as exc_info:
            await provider.get_historical_candles("UNKNOWN", "M15")
        assert exc_info.value.status_code == 400
        assert "Symbol 'UNKNOWN' not found" in str(exc_info.value)


# ─── 3. Network Timeout Tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_network_timeout():
    """Test that httpx.TimeoutException is cleanly wrapped in ProviderTimeoutError."""
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("Connection timed out after 10.0s")

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(ProviderTimeoutError) as exc_info:
            await provider.get_latest_price("XAUUSD")
        assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_network_connection_error():
    """Test that connection failure is wrapped in ProviderConnectionError."""
    def handler(request: httpx.Request):
        raise httpx.ConnectError("Failed to resolve host api.twelvedata.com")

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(ProviderConnectionError) as exc_info:
            await provider.get_historical_candles("XAUUSD")
        assert "Network error" in str(exc_info.value)


# ─── 4. Missing Candle / Empty Response Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_empty_candle_response():
    """Test provider handles empty candle values array cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"values": [], "status": "ok"})

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        candles = await provider.get_historical_candles("XAUUSD", "M15")
        assert candles == []

        latest = await provider.get_latest_candle("XAUUSD", "M15")
        assert latest is None


def test_missing_candle_gap_detection():
    """Verify that gaps between consecutive M15 candles can be detected."""
    t1 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)  # missing 10:15

    c1 = NormalizedCandle.create(timestamp=t1, open=2350, high=2355, low=2348, close=2352)
    c3 = NormalizedCandle.create(timestamp=t3, open=2352, high=2358, low=2350, close=2356)

    # Gap between c1 and c3 is 30 mins instead of 15 mins
    delta = (c3.timestamp - c1.timestamp).total_seconds() / 60
    assert delta == 30
    assert delta > 15  # Gap detected


# ─── 5. Duplicate Candle Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_candle_deduplication():
    """
    Test that when the provider returns duplicate candles with the same timestamp,
    they are deduplicated into exactly one candle per boundary.
    """
    raw_payload = {
        "values": [
            {
                "datetime": "2026-09-04 10:00:00",
                "open": "2490.00",
                "high": "2495.00",
                "low": "2488.00",
                "close": "2494.00",
                "volume": "100",
            },
            # Exact duplicate timestamp
            {
                "datetime": "2026-09-04 10:00:00",
                "open": "2490.00",
                "high": "2495.00",
                "low": "2488.00",
                "close": "2494.00",
                "volume": "100",
            },
            {
                "datetime": "2026-09-04 09:45:00",
                "open": "2485.00",
                "high": "2491.00",
                "low": "2484.00",
                "close": "2489.50",
                "volume": "120",
            },
        ],
        "status": "ok",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        candles = await provider.get_historical_candles("XAUUSD", "M15")

        # Must have 2 unique candles, not 3
        assert len(candles) == 2
        timestamps = [c.timestamp for c in candles]
        assert len(timestamps) == len(set(timestamps))


# ─── 6. Malformed Data Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_malformed_missing_close_key():
    """Test candle missing required 'close' field raises MalformedDataError."""
    raw_payload = {
        "values": [
            {
                "datetime": "2026-09-04 10:00:00",
                "open": "2490.00",
                "high": "2495.00",
                "low": "2488.00",
                # 'close' is deliberately missing
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(MalformedDataError) as exc_info:
            await provider.get_historical_candles("XAUUSD")
        assert "missing required field 'close'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_non_numeric_price():
    """Test candle with non-numeric value raises MalformedDataError."""
    raw_payload = {
        "values": [
            {
                "datetime": "2026-09-04 10:00:00",
                "open": "2490.00",
                "high": "NOT_A_NUMBER",
                "low": "2488.00",
                "close": "2493.00",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(MalformedDataError) as exc_info:
            await provider.get_historical_candles("XAUUSD")
        assert "Invalid numeric value" in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_invalid_timestamp():
    """Test candle with corrupted datetime string raises MalformedDataError."""
    raw_payload = {
        "values": [
            {
                "datetime": "corrupted-date-format",
                "open": "2490.00",
                "high": "2495.00",
                "low": "2488.00",
                "close": "2493.00",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_payload)

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(MalformedDataError) as exc_info:
            await provider.get_historical_candles("XAUUSD")
        assert "Invalid candle timestamp format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_non_json_response():
    """Test non-JSON HTML response (e.g. 502 Bad Gateway HTML) raises error."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>502 Bad Gateway</body></html>")

    async with make_mock_client(handler) as client:
        provider = TwelveDataXAUUSDProvider(client=client)
        with pytest.raises(MalformedDataError) as exc_info:
            await provider.get_latest_price("XAUUSD")
        assert "Failed to parse JSON" in str(exc_info.value)


# ─── 7. Mock Provider Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_generates_valid_candles():
    """Verify MockXAUUSDProvider generates valid synthetic candles offline."""
    mock = MockXAUUSDProvider(base_price=2350.0)
    candles = await mock.get_historical_candles(limit=20, timeframe="M15")

    assert len(candles) == 20
    # Strictly sorted chronologically
    for i in range(len(candles) - 1):
        assert candles[i].timestamp < candles[i + 1].timestamp

    # Price range check around base_price
    for c in candles:
        assert 2300.0 <= c.close <= 2400.0
        assert c.high >= max(c.open, c.close)
        assert c.low <= min(c.open, c.close)
        assert c.timestamp.tzinfo == timezone.utc

    latest = await mock.get_latest_candle()
    assert latest is not None
    assert latest.timestamp == candles[-1].timestamp


@pytest.mark.asyncio
async def test_factory_returns_provider():
    """Test factory creates expected provider instances."""
    mock_p = get_market_provider("mock")
    assert isinstance(mock_p, MockXAUUSDProvider)

    td_p = get_market_provider("twelvedata")
    assert isinstance(td_p, TwelveDataXAUUSDProvider)
    assert isinstance(td_p, BaseMarketDataProvider)
