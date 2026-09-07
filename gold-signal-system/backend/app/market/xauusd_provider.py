"""
Twelve Data XAUUSD Market Data Provider implementation.

Twelve Data was selected for the following reasons:
1. Native XAU/USD (Spot Gold) coverage under FOREX/Metals.
2. Direct M15 interval support ('15min') — no client-side bar aggregation needed.
3. Generous free tier (800 API requests/day, 8/minute), ideal for periodic M15 polling.
4. Comprehensive and stable REST API with clear error statuses.
5. UTC datetime format with standard OHLCV fields.

This module also provides MockXAUUSDProvider for offline development and testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence

import httpx

from app.config import get_settings
from app.market.base_provider import BaseMarketDataProvider
from app.market.models import (
    MalformedDataError,
    NormalizedCandle,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
    align_to_boundary,
)

logger = logging.getLogger(__name__)

# Map internal timeframe notation to Twelve Data interval parameter
TIMEFRAME_MAP = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1day",
}


def format_symbol_for_twelvedata(symbol: str) -> str:
    """
    Twelve Data expects currency/metal pairs in 'BASE/QUOTE' format.
    e.g. 'XAUUSD' -> 'XAU/USD'.
    """
    clean = symbol.strip().upper()
    if "/" in clean:
        return clean
    if clean.startswith("XAU") and len(clean) == 6:
        return f"{clean[:3]}/{clean[3:]}"
    return clean


class TwelveDataXAUUSDProvider(BaseMarketDataProvider):
    """
    Twelve Data REST API client for XAUUSD market data.
    """

    DEFAULT_BASE_URL = "https://api.twelvedata.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.data_provider_api_key
        self.base_url = (base_url or settings.data_provider_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=self.timeout_seconds)

    async def get_latest_price(self, symbol: str = "XAUUSD") -> float:
        """
        Fetch real-time spot price from /price endpoint.
        Returns float price.
        """
        td_symbol = format_symbol_for_twelvedata(symbol)
        url = f"{self.base_url}/price"
        params = {"symbol": td_symbol}
        if self.api_key:
            params["apikey"] = self.api_key

        data = await self._get_json(url, params)

        if "price" not in data:
            raise MalformedDataError(
                f"Twelve Data /price response missing 'price' field: {data}"
            )

        try:
            return float(data["price"])
        except (ValueError, TypeError) as exc:
            raise MalformedDataError(
                f"Invalid price value '{data.get('price')}': {exc}"
            ) from exc

    async def get_historical_candles(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Sequence[NormalizedCandle]:
        """
        Fetch historical candles from /time_series endpoint.
        Parses, aligns boundaries, deduplicates, and sorts chronologically.
        """
        td_symbol = format_symbol_for_twelvedata(symbol)
        interval = TIMEFRAME_MAP.get(timeframe.upper(), "15min")

        url = f"{self.base_url}/time_series"
        params = {
            "symbol": td_symbol,
            "interval": interval,
            "outputsize": min(max(1, limit), 5000),
            "timezone": "UTC",
        }
        if self.api_key:
            params["apikey"] = self.api_key
        if start_time:
            params["start_date"] = start_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if end_time:
            params["end_date"] = end_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        data = await self._get_json(url, params)

        # Twelve Data returns {"values": [...], "status": "ok"}
        raw_values = data.get("values")
        if raw_values is None:
            # Check if there is an error in the response
            if data.get("status") == "error":
                raise ProviderResponseError(
                    f"Twelve Data error: {data.get('message')}",
                    status_code=data.get("code"),
                    details=data,
                )
            raise MalformedDataError(
                f"Twelve Data response missing 'values' array: {data}"
            )

        candles_by_ts: dict[datetime, NormalizedCandle] = {}
        for raw in raw_values:
            candle = self._parse_single_candle(raw, timeframe)
            # Deduplicate by aligned timestamp
            candles_by_ts[candle.timestamp] = candle

        # Sort chronologically ascending (oldest first)
        sorted_candles = sorted(candles_by_ts.values(), key=lambda c: c.timestamp)

        # Apply client-side time filtering if specified
        if start_time:
            st_utc = (
                start_time.astimezone(timezone.utc)
                if start_time.tzinfo
                else start_time.replace(tzinfo=timezone.utc)
            )
            sorted_candles = [c for c in sorted_candles if c.timestamp >= st_utc]
        if end_time:
            et_utc = (
                end_time.astimezone(timezone.utc)
                if end_time.tzinfo
                else end_time.replace(tzinfo=timezone.utc)
            )
            sorted_candles = [c for c in sorted_candles if c.timestamp <= et_utc]

        return sorted_candles

    async def get_latest_candle(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
    ) -> Optional[NormalizedCandle]:
        """Fetch the most recent single candle."""
        candles = await self.get_historical_candles(symbol=symbol, timeframe=timeframe, limit=1)
        if not candles:
            return None
        return candles[-1]

    def _parse_single_candle(self, raw: dict, timeframe: str) -> NormalizedCandle:
        """
        Parse raw Twelve Data candle object:
        {"datetime": "...", "open": "...", "high": "...", "low": "...", "close": "...", "volume": "..."}
        """
        required_keys = ("datetime", "open", "high", "low", "close")
        for key in required_keys:
            if key not in raw or raw[key] is None:
                raise MalformedDataError(f"Candle data missing required field '{key}': {raw}")

        raw_dt = raw["datetime"]
        try:
            if "T" in raw_dt:
                dt = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception as exc:
            raise MalformedDataError(f"Invalid candle timestamp format '{raw_dt}': {exc}") from exc

        try:
            open_p = float(raw["open"])
            high_p = float(raw["high"])
            low_p = float(raw["low"])
            close_p = float(raw["close"])
            volume = float(raw.get("volume") or 0.0)
        except (ValueError, TypeError) as exc:
            raise MalformedDataError(f"Invalid numeric value in candle data {raw}: {exc}") from exc

        return NormalizedCandle.create(
            timestamp=dt,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
            timeframe=timeframe,
        )

    async def _get_json(self, url: str, params: dict) -> dict:
        """Send GET request and handle HTTP / network / timeout errors."""
        try:
            response = await self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Request to {url} timed out: {exc}") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderConnectionError(f"Network error connecting to {url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"HTTP client error requesting {url}: {exc}") from exc

        if response.status_code != 200:
            raise ProviderResponseError(
                f"Twelve Data returned HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except Exception as exc:
            raise MalformedDataError(f"Failed to parse JSON response from {url}: {exc}") from exc

        # Twelve Data error payload can arrive with HTTP 200: {"status": "error", "message": "..."}
        if isinstance(data, dict) and data.get("status") == "error":
            raise ProviderResponseError(
                f"Twelve Data API error ({data.get('code')}): {data.get('message')}",
                status_code=data.get("code"),
                details=data,
            )

        return data

    async def close(self) -> None:
        """Close underlying HTTP client if created internally."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()


# ─── Mock Provider (for offline development and unit tests) ───────────────────

class MockXAUUSDProvider(BaseMarketDataProvider):
    """
    Synthetic market data provider for tests and offline development.
    Generates realistic XAUUSD M15 candles deterministically.
    """

    def __init__(
        self,
        base_price: float = 2350.0,
        error_on_next: Optional[Exception] = None,
        candle_data: Optional[list[NormalizedCandle]] = None,
    ) -> None:
        self.base_price = base_price
        self.error_on_next = error_on_next
        self.candle_data = candle_data or []

    async def get_latest_price(self, symbol: str = "XAUUSD") -> float:
        if self.error_on_next:
            err = self.error_on_next
            self.error_on_next = None
            raise err
        if self.candle_data:
            return self.candle_data[-1].close
        return self.base_price

    async def get_historical_candles(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Sequence[NormalizedCandle]:
        if self.error_on_next:
            err = self.error_on_next
            self.error_on_next = None
            raise err

        if self.candle_data:
            candles = list(self.candle_data)
            if start_time:
                st = (
                    start_time.astimezone(timezone.utc)
                    if start_time.tzinfo
                    else start_time.replace(tzinfo=timezone.utc)
                )
                candles = [c for c in candles if c.timestamp >= st]
            if end_time:
                et = (
                    end_time.astimezone(timezone.utc)
                    if end_time.tzinfo
                    else end_time.replace(tzinfo=timezone.utc)
                )
                candles = [c for c in candles if c.timestamp <= et]
            return candles[-limit:]

        # Generate synthetic candles
        import math
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        aligned_now = align_to_boundary(now, timeframe)
        candles = []
        for i in range(limit):
            ts = aligned_now - timedelta(minutes=(limit - 1 - i) * 15)
            # Gentle sinusoidal price walk around base_price
            price_offset = math.sin(i * 0.3) * 10.0
            o = self.base_price + price_offset
            c = o + (math.cos(i * 0.4) * 2.5)
            h = max(o, c) + 1.8
            low_p = min(o, c) - 1.5
            v = 150.0 + (i % 20) * 10.0
            candles.append(NormalizedCandle.create(
                timestamp=ts,
                open=round(o, 2),
                high=round(h, 2),
                low=round(low_p, 2),
                close=round(c, 2),
                volume=v,
                timeframe=timeframe,
            ))
        return candles

    async def get_latest_candle(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
    ) -> Optional[NormalizedCandle]:
        candles = await self.get_historical_candles(symbol=symbol, timeframe=timeframe, limit=1)
        return candles[-1] if candles else None

    async def close(self) -> None:
        pass


class MT5PushProvider(BaseMarketDataProvider):
    """
    Inbound MT5 Provider.
    Live candles are delivered via POST /api/market/candle by the MT5 Expert Advisor.
    Background polling is a no-op since candles arrive via live push from MetaTrader 5.
    """

    async def get_latest_price(self, symbol: str) -> float:
        return 0.0

    async def get_historical_candles(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        limit: int = 100,
    ) -> Sequence[NormalizedCandle]:
        return []

    async def get_latest_candle(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
    ) -> Optional[NormalizedCandle]:
        return None

    async def close(self) -> None:
        pass


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_market_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseMarketDataProvider:
    """
    Factory to construct the active market data provider.
    Supports TwelveData, MT5 (direct broker push), and Mock providers.
    """
    settings = get_settings()
    name = (provider_name or settings.data_provider).lower()

    if name == "mock":
        return MockXAUUSDProvider()

    if name == "mt5":
        return MT5PushProvider()

    # Default to Twelve Data
    key = api_key or settings.data_provider_api_key
    return TwelveDataXAUUSDProvider(api_key=key)


# Convenient alias
XAUUSDProvider = TwelveDataXAUUSDProvider
