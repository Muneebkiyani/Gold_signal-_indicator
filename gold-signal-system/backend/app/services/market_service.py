"""
Market Service — fault-isolated wrapper around the market data provider.

Responsibilities:
  - Fetch the latest OHLCV candles from the configured provider.
  - Absorb all network / provider errors and return an empty list.
  - Emit structured log lines so the scheduler can stay clean.

This module intentionally does NOT raise exceptions. Every error is caught,
logged with the ``ERROR`` tag, and an empty candle list is returned so the
scheduler loop can simply continue to the next tick.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.market.base_provider import BaseMarketDataProvider
from app.market.models import NormalizedCandle
from app.config import get_settings

logger = logging.getLogger(__name__)


class MarketService:
    """
    Thin, fault-tolerant wrapper around a ``BaseMarketDataProvider``.

    Instantiate once and reuse across ticks.
    """

    def __init__(self, provider: BaseMarketDataProvider) -> None:
        self._provider = provider
        self._settings = get_settings()

    # ── Public API ────────────────────────────────────────────────────────────

    async def fetch_latest_candles(
        self,
        limit: Optional[int] = None,
    ) -> List[NormalizedCandle]:
        """
        Fetch the most recent *limit* candles from the provider.

        Returns an empty list on any error so callers never have to handle
        provider failures.
        """
        effective_limit = limit or self._settings.candle_history_limit
        symbol = self._settings.symbol
        timeframe = self._settings.timeframe

        logger.info(
            "MARKET DATA UPDATE | Fetching %d candles for %s %s",
            effective_limit,
            symbol,
            timeframe,
        )

        try:
            candles = await self._provider.get_historical_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=effective_limit,
            )
            logger.info(
                "MARKET DATA UPDATE | Received %d candles for %s %s",
                len(candles),
                symbol,
                timeframe,
            )
            return list(candles)

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "ERROR | Market data fetch failed for %s %s: %s",
                symbol,
                timeframe,
                exc,
            )
            return []
