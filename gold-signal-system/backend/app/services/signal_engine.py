"""
Signal Engine — Orchestrates Market Data, Candle Management, Indicator Calculations,
and Pine Script Strategy Execution into a unified processing pipeline.

Workflow per completed M15 candle:
  1. Candle completed check (via M15CandleManager)
  2. Indicator calculations (via IndicatorEngine)
  3. Strategy evaluation:
     - EMA/RSI/ADX evaluation (independent source)
     - SMA 81 evaluation (independent source)
  4. Signal filtering:
     - BUY / SELL always captured
     - NO_ENTRY transitions captured
     - WAIT states ignored for DB storage (prevents DB bloating)
  5. Duplicate protection (in-memory tracking + DB UniqueConstraint uq_signal_bar)
  6. Persistence to database
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.signal import (
    create_signal,
    get_latest_signal,
    update_telegram_status,
)
from app.market.base_provider import BaseMarketDataProvider
from app.market.candle_manager import M15CandleManager
from app.market.models import NormalizedCandle
from app.models.enums import SignalType
from app.models.signal import Signal
from app.strategy.engine import IndicatorEngine
from app.strategy.strategy import StrategySignal, evaluate_strategies
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Unified signal engine coordinating market data ingestion, candle boundary
    validation, technical indicator computations, strategy logic, and database persistence.
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        provider: Optional[BaseMarketDataProvider] = None,
        candle_manager: Optional[M15CandleManager] = None,
        indicator_engine: Optional[IndicatorEngine] = None,
        store_no_entry: bool = True,
        store_wait: bool = False,
    ) -> None:
        settings = get_settings()
        self.symbol = (symbol or settings.symbol).upper()
        self.timeframe = (timeframe or settings.timeframe).upper()

        self.candle_manager = candle_manager or M15CandleManager(
            symbol=self.symbol,
            provider=provider,
        )
        self.indicator_engine = indicator_engine or IndicatorEngine()
        self.telegram_service = TelegramService()

        self.store_no_entry = store_no_entry
        self.store_wait = store_wait

        # Last candle timestamp evaluated by the strategy engine
        self.last_evaluated_candle_time: Optional[datetime] = None

    # ─── Startup / Initialization & Recovery ──────────────────────────────────

    async def initialize(self, session: AsyncSession, history_limit: int = 150) -> None:
        """
        Recover state from the database on backend startup:
          - Load recent candles into memory to warm up indicators (SMA 81 needs >= 81 bars).
          - Restore last_evaluated_candle_time to prevent duplicate signal generation.
        """
        # Warm up candle manager from database
        await self.candle_manager.initialize_from_db(session, limit=history_limit)

        if self.candle_manager.last_processed_candle_time is not None:
            self.last_evaluated_candle_time = self.candle_manager.last_processed_candle_time

        # Cross-check latest signal in DB
        latest_sig = await get_latest_signal(session, symbol=self.symbol, timeframe=self.timeframe)
        if latest_sig and latest_sig.candle_time:
            sig_time = latest_sig.candle_time
            if sig_time.tzinfo is None:
                sig_time = sig_time.replace(tzinfo=timezone.utc)
            if (
                self.last_evaluated_candle_time is None
                or sig_time > self.last_evaluated_candle_time
            ):
                self.last_evaluated_candle_time = sig_time

        logger.info(
            "[%s %s] SignalEngine initialized. Warmed up with %d candles. Last evaluated bar: %s",
            self.symbol,
            self.timeframe,
            len(self.candle_manager.candles),
            self.last_evaluated_candle_time.isoformat()
            if self.last_evaluated_candle_time else "None",
        )

    # ─── Candle Evaluation Pipeline ───────────────────────────────────────────

    async def process_candle(
        self,
        candle: NormalizedCandle,
        session: AsyncSession,
        current_time: Optional[datetime] = None,
    ) -> list[Signal]:
        """
        Process an incoming candle through the entire pipeline:
          1. Validation & completion check via CandleManager
          2. Duplicate evaluation check
          3. Indicator generation
          4. Strategy evaluation (EMA_RSI_ADX and SMA_81)
          5. Filter signals for storage
          6. Persist to DB with unique constraint protection
        """
        # Step 1: CandleManager processes, completes, and saves candle to DB
        completed_candle = await self.candle_manager.process_candle(
            candle=candle,
            current_time=current_time,
            session=session,
        )
        if completed_candle is None:
            # Unfinished, duplicate, or out-of-order candle
            return []

        # Step 2: Prevent duplicate evaluation of the same candle
        if self.last_evaluated_candle_time is not None:
            if completed_candle.timestamp <= self.last_evaluated_candle_time:
                logger.debug(
                    "[%s] Candle at %s already evaluated. Skipping signal generation.",
                    self.symbol,
                    completed_candle.timestamp.isoformat(),
                )
                return []

        # Step 3: Run strategy evaluation over current candle history
        strategy_signals: list[StrategySignal] = evaluate_strategies(
            candles=self.candle_manager.candles,
            symbol=self.symbol,
            timeframe=self.timeframe,
            engine=self.indicator_engine,
        )

        persisted_signals: list[Signal] = []

        # Step 4 & 5: Filter and persist
        for strat_sig in strategy_signals:
            should_store = False

            if strat_sig.signal_type in (SignalType.BUY, SignalType.SELL):
                should_store = True
            elif strat_sig.signal_type == SignalType.NO_ENTRY and self.store_no_entry:
                should_store = True
            elif strat_sig.signal_type == SignalType.WAIT and self.store_wait:
                should_store = True

            if should_store:
                db_model = strat_sig.to_db_signal()
                # Step 6: Insert into DB with duplicate protection
                saved = await create_signal(session, db_model, ignore_duplicates=True)

                # Step 7: Send Telegram Alert
                if get_settings().telegram_enabled:
                    msg_text = self.telegram_service.format_signal(saved)
                    if msg_text:
                        success, error_msg = await self.telegram_service.send_message(
                            msg_text
                        )
                        saved = await update_telegram_status(
                            session=session,
                            signal_id=saved.id,
                            sent=success,
                            error=error_msg
                        )

                persisted_signals.append(saved)
                logger.info(
                    "[%s %s] Signal generated & stored: %s from %s @ %.2f (Bar: %s)",
                    self.symbol,
                    self.timeframe,
                    strat_sig.signal_type.value,
                    strat_sig.signal_source.value,
                    strat_sig.price,
                    strat_sig.candle_time.isoformat(),
                )

        # Update last evaluated time
        self.last_evaluated_candle_time = completed_candle.timestamp
        return persisted_signals

    async def process_candles(
        self,
        candles: Sequence[NormalizedCandle],
        session: AsyncSession,
        current_time: Optional[datetime] = None,
    ) -> list[Signal]:
        """
        Process multiple candles in chronological order.
        Returns all newly generated and persisted signals.
        """
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)
        all_signals: list[Signal] = []

        for candle in sorted_candles:
            sigs = await self.process_candle(
                candle=candle,
                session=session,
                current_time=current_time,
            )
            all_signals.extend(sigs)

        return all_signals

    async def sync_and_evaluate(
        self,
        session: AsyncSession,
        limit: int = 100,
        current_time: Optional[datetime] = None,
    ) -> list[Signal]:
        """
        Poll market data provider for new candles and evaluate signals.
        """
        if self.candle_manager.provider is None:
            logger.warning("No market data provider configured on CandleManager.")
            return []

        raw_candles = await self.candle_manager.provider.get_historical_candles(
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=limit,
        )

        return await self.process_candles(
            candles=raw_candles,
            session=session,
            current_time=current_time,
        )
