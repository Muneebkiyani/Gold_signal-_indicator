"""
Abstract base class for market data providers.

Decouples the strategy and alert system from any specific data vendor.
Any provider implementing this interface can be substituted with zero changes
to strategy calculations or database models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from app.market.models import NormalizedCandle


class BaseMarketDataProvider(ABC):
    """
    Abstract interface for market data providers.

    All methods return normalized data models.
    Implementations must raise exceptions derived from MarketDataError.
    """

    @abstractmethod
    async def get_latest_price(self, symbol: str) -> float:
        """
        Fetch the current market spot/tick price for a given symbol.

        Args:
            symbol: Financial instrument symbol (e.g. 'XAUUSD' or 'XAU/USD').

        Returns:
            Current price as a float.

        Raises:
            ProviderTimeoutError: When the request times out.
            ProviderConnectionError: When network connection fails.
            ProviderResponseError: When API returns an error status.
            MalformedDataError: When response payload is missing or unparseable.
        """
        ...

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: str = "M15",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Sequence[NormalizedCandle]:
        """
        Fetch historical OHLCV candles, guaranteed to be:
          - Sorted chronologically ascending (oldest first, newest last)
          - Normalized with deterministic UTC open timestamps
          - Deduplicated by timestamp

        Args:
            symbol: Financial instrument symbol (e.g. 'XAUUSD').
            timeframe: Candle interval (default: 'M15').
            limit: Maximum number of candles to return (default: 100).
            start_time: Optional UTC datetime filter.
            end_time: Optional UTC datetime filter.

        Returns:
            Sequence of NormalizedCandle objects.

        Raises:
            ProviderTimeoutError: When the request times out.
            ProviderConnectionError: When network connection fails.
            ProviderResponseError: When API returns an error status.
            MalformedDataError: When response payload is invalid.
        """
        ...

    @abstractmethod
    async def get_latest_candle(
        self,
        symbol: str,
        timeframe: str = "M15",
    ) -> Optional[NormalizedCandle]:
        """
        Fetch the single most recent candle for the given symbol and timeframe.

        Args:
            symbol: Financial instrument symbol (e.g. 'XAUUSD').
            timeframe: Candle interval (default: 'M15').

        Returns:
            The most recent NormalizedCandle, or None if no candle data exists.

        Raises:
            MarketDataError subclasses on failures.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release underlying network resources / HTTP client sessions."""
        ...

    async def __aenter__(self) -> BaseMarketDataProvider:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
