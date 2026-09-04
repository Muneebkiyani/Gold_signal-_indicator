"""
M15 Candle Manager.

Core responsibilities:
1. Ingest normalized market data.
2. Construct / aggregate M15 candles if fed sub-period bars (e.g. M1 or M5).
3. Strictly distinguish unfinished vs. completed M15 candles.
4. Normalize all timestamps to UTC.
5. Maintain strictly ascending chronological candle ordering.
6. Enforce duplicate prevention:
     Maintain `last_processed_candle_time`.
     Reject any candle with `candle_time <= last_processed_candle_time`.
7. Identify the latest completed candle.
8. Persistence & Restart survival:
     On restart / initialization, load recent candles from database,
     restore `last_processed_candle_time`, and avoid reprocessing previously handled bars.

CRITICAL RULE:
A 10:00 -> 10:15 candle has open timestamp 10:00:00 UTC.
It is ONLY completed after 10:15:00 UTC.
Never evaluate signals on an unfinished candle.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.candle import (
    get_candles as db_get_candles,
    save_candles as db_save_candles,
)
from app.market.base_provider import BaseMarketDataProvider
from app.market.models import (
    NormalizedCandle,
    align_to_m15_boundary,
)
from app.models.candle import Candle

logger = logging.getLogger(__name__)

CANDLE_DURATION_M15 = timedelta(minutes=15)


def db_to_normalized(candle: Candle) -> NormalizedCandle:
    """Convert database Candle to NormalizedCandle with timezone-aware UTC timestamp."""
    ts = candle.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    return NormalizedCandle(
        timestamp=ts,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def normalized_to_db(nc: NormalizedCandle, symbol: str, timeframe: str) -> Candle:
    """Convert NormalizedCandle to database Candle model."""
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=nc.timestamp,
        open=nc.open,
        high=nc.high,
        low=nc.low,
        close=nc.close,
        volume=nc.volume,
    )


class M15CandleManager:
    """
    Manages M15 candles for a specific symbol.

    Guarantees that only completed, verified, non-duplicate M15 candles
    are returned for strategy indicator calculations and alert triggers.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        provider: Optional[BaseMarketDataProvider] = None,
        max_in_memory_candles: int = 500,
    ) -> None:
        self.symbol = symbol.upper()
        self.timeframe = "M15"
        self.provider = provider
        self.max_in_memory_candles = max_in_memory_candles

        # In-memory ordered candle history (chronological ascending)
        self._candles: list[NormalizedCandle] = []

        # Timestamp of the last candle that was evaluated / processed
        self.last_processed_candle_time: Optional[datetime] = None

    @property
    def candles(self) -> list[NormalizedCandle]:
        """Return a copy of current in-memory candles."""
        return list(self._candles)

    # ─── Initialization & Persistence ─────────────────────────────────────────

    async def initialize_from_db(self, session: AsyncSession, limit: int = 100) -> None:
        """
        Load historical candles on startup to restore state and survive restart.
        Restores `last_processed_candle_time` to the latest completed candle.
        """
        db_candles = await db_get_candles(
            session=session,
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=limit,
            ascending=True,
        )

        self._candles.clear()
        for c in db_candles:
            self._candles.append(db_to_normalized(c))

        if self._candles:
            self.last_processed_candle_time = self._candles[-1].timestamp
            logger.info(
                "[%s M15] Initialized from DB: %d candles loaded. last_processed_candle_time=%s",
                self.symbol,
                len(self._candles),
                self.last_processed_candle_time.isoformat(),
            )
        else:
            self.last_processed_candle_time = None
            logger.info("[%s M15] Initialized from DB: 0 candles found.", self.symbol)

    async def sync_from_provider(
        self,
        session: Optional[AsyncSession] = None,
        limit: int = 100,
        current_time: Optional[datetime] = None,
    ) -> list[NormalizedCandle]:
        """
        Fetch historical candles from provider, persist new ones to database,
        and process any newly completed candles.
        """
        if self.provider is None:
            logger.warning("No market data provider configured for %s", self.symbol)
            return []

        raw_candles = await self.provider.get_historical_candles(
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=limit,
        )

        return await self.process_candles(
            candles=raw_candles,
            current_time=current_time,
            session=session,
        )

    # ─── Completion & Boundary Checks ─────────────────────────────────────────

    @staticmethod
    def is_candle_completed(
        candle: NormalizedCandle,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if an M15 candle is strictly completed.

        For candle open at 10:00:00 UTC:
          Close time = 10:15:00 UTC.
          Completed IF current_time >= 10:15:00 UTC.
        """
        now_utc = current_time or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        candle_close_time = candle.timestamp + CANDLE_DURATION_M15
        return now_utc >= candle_close_time

    def get_latest_completed_candle(
        self,
        current_time: Optional[datetime] = None,
    ) -> Optional[NormalizedCandle]:
        """
        Return the latest completed candle from in-memory cache, or None.
        """
        for candle in reversed(self._candles):
            if self.is_candle_completed(candle, current_time):
                return candle
        return None

    # ─── Candle Processing & Deduplication ───────────────────────────────────

    async def process_candle(
        self,
        candle: NormalizedCandle,
        current_time: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> Optional[NormalizedCandle]:
        """
        Process a single incoming normalized candle.

        Returns:
            The NormalizedCandle IF it is completed, newly verified, and not duplicate.
            None IF the candle is unfinished, duplicate, or out-of-order.
        """
        # Ensure UTC and M15 boundary alignment
        aligned_ts = align_to_m15_boundary(candle.timestamp)
        normalized = NormalizedCandle.create(
            timestamp=aligned_ts,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            timeframe=self.timeframe,
        )

        # 1. Reject unfinished candles
        if not self.is_candle_completed(normalized, current_time):
            logger.debug(
                "[%s M15] Candle at %s is unfinished (closes at %s). Skipping.",
                self.symbol,
                normalized.timestamp.isoformat(),
                (normalized.timestamp + CANDLE_DURATION_M15).isoformat(),
            )
            return None

        # 2. Reject duplicates and past bars
        if self.last_processed_candle_time is not None:
            if normalized.timestamp <= self.last_processed_candle_time:
                logger.debug(
                    "[%s M15] Candle at %s already processed (last=%s). Skipping duplicate.",
                    self.symbol,
                    normalized.timestamp.isoformat(),
                    self.last_processed_candle_time.isoformat(),
                )
                return None

        # 3. Handle out-of-order: verify chronological order
        if self._candles and normalized.timestamp < self._candles[-1].timestamp:
            logger.warning(
                "[%s M15] Out-of-order candle received (%s < %s). Ignored.",
                self.symbol,
                normalized.timestamp.isoformat(),
                self._candles[-1].timestamp.isoformat(),
            )
            return None

        # 4. If same timestamp as the last in-memory candle, replace it (e.g. final close update)
        if self._candles and self._candles[-1].timestamp == normalized.timestamp:
            self._candles[-1] = normalized
        else:
            self._candles.append(normalized)

        # Prune memory buffer if exceeding capacity
        if len(self._candles) > self.max_in_memory_candles:
            self._candles = self._candles[-self.max_in_memory_candles:]

        # 5. Persist to database if an active session is provided
        if session is not None:
            db_candle = normalized_to_db(normalized, self.symbol, self.timeframe)
            await db_save_candles(session, [db_candle])

        # 6. Update last_processed_candle_time
        self.last_processed_candle_time = normalized.timestamp
        logger.info(
            "[%s M15] Completed candle accepted: %s (O:%.2f H:%.2f L:%.2f C:%.2f V:%.1f)",
            self.symbol,
            normalized.timestamp.isoformat(),
            normalized.open,
            normalized.high,
            normalized.low,
            normalized.close,
            normalized.volume,
        )
        return normalized

    async def process_candles(
        self,
        candles: Sequence[NormalizedCandle],
        current_time: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> list[NormalizedCandle]:
        """
        Process a batch of incoming candles in chronological order.
        Returns list of newly completed candles ready for strategy evaluation.
        """
        # Sort chronologically ascending
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)

        newly_completed: list[NormalizedCandle] = []
        for candle in sorted_candles:
            res = await self.process_candle(candle, current_time=current_time, session=session)
            if res is not None:
                newly_completed.append(res)

        return newly_completed

    # ─── Construction from Smaller Sub-Period Candles ─────────────────────────

    @staticmethod
    def construct_m15_from_smaller_candles(
        smaller_candles: Sequence[NormalizedCandle],
    ) -> list[NormalizedCandle]:
        """
        Aggregate smaller period candles (e.g. M1 or M5) into standard M15 candles.

        Rules for M15 candle at open timestamp T (e.g. 10:00):
          - Covers [T, T + 15m)
          - open: open of the first sub-candle
          - high: maximum high of all sub-candles in the bucket
          - low: minimum low of all sub-candles in the bucket
          - close: close of the last sub-candle
          - volume: sum of volume of all sub-candles
        """
        if not smaller_candles:
            return []

        # Group by M15 boundary
        buckets: dict[datetime, list[NormalizedCandle]] = {}
        for c in sorted(smaller_candles, key=lambda x: x.timestamp):
            b_ts = align_to_m15_boundary(c.timestamp)
            if b_ts not in buckets:
                buckets[b_ts] = []
            buckets[b_ts].append(c)

        m15_candles: list[NormalizedCandle] = []
        for b_ts, group in sorted(buckets.items(), key=lambda x: x[0]):
            first_c = group[0]
            last_c = group[-1]
            open_p = first_c.open
            close_p = last_c.close
            high_p = max(c.high for c in group)
            low_p = min(c.low for c in group)
            vol = sum(c.volume for c in group)

            m15_candles.append(
                NormalizedCandle.create(
                    timestamp=b_ts,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=vol,
                    timeframe="M15",
                )
            )

        return m15_candles
