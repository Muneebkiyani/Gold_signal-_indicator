"""
Signal Scheduler — background asyncio task that drives the polling loop.

Lifecycle::

    scheduler = SignalScheduler(market_service, signal_service)
    await scheduler.start(session_factory)   # FastAPI lifespan startup
    # ... server runs ...
    await scheduler.stop()                   # FastAPI lifespan shutdown

The loop is deliberately simple:

    while running:
        try:
            candles = await market_service.fetch_latest_candles()
            await signal_service.evaluate(candles, session)
        except Exception:
            log ERROR, continue
        await sleep(POLL_INTERVAL_SECONDS)

All exceptions inside the tick body are caught and logged; the loop
never exits due to an application error.  It exits only when
``stop()`` is called (which cancels the task).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.services.market_service import MarketService
from app.services.signal_service import SignalService

logger = logging.getLogger(__name__)

# Type alias for the session factory callable
SessionFactory = Callable[[], AsyncSession]


class SignalScheduler:
    """
    Owns the background ``asyncio.Task`` that continuously polls the market
    data provider, evaluates signals, and dispatches Telegram alerts.
    """

    def __init__(
        self,
        market_service: MarketService,
        signal_service: SignalService,
    ) -> None:
        self._market_service = market_service
        self._signal_service = signal_service
        self._settings = get_settings()
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._session_factory: Optional[async_sessionmaker] = None  # type: ignore[type-arg]

    # ── Public lifecycle ──────────────────────────────────────────────────────

    async def start(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        """
        Initialize state from the database then launch the polling loop
        as a background asyncio Task.
        """
        if self._task is not None and not self._task.done():
            logger.warning("Scheduler already running — ignoring duplicate start()")
            return

        self._session_factory = session_factory
        logger.info("SYSTEM STARTED | Initializing signal worker")

        # Warm-up: load history and recover last-evaluated candle time
        async with session_factory() as session:
            await self._signal_service.initialize(session)

        logger.info(
            "SYSTEM STARTED | Worker ready — polling every %ds",
            self._settings.poll_interval_seconds,
        )
        self._task = asyncio.create_task(
            self._run_loop(), name="signal_scheduler_loop"
        )

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish cleanly."""
        if self._task is None or self._task.done():
            return
        logger.info("SHUTTING DOWN | Cancelling signal worker task")
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info("SHUTTING DOWN | Signal worker stopped")

    # ── Internal loop ─────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """
        Main polling loop. Runs until the task is cancelled.

        Each tick:
          1. Fetch market data (errors → empty list, loop continues).
          2. Evaluate signals (errors → empty list, loop continues).
          3. Sleep for POLL_INTERVAL_SECONDS.
        """
        logger.info(
            "SYSTEM STARTED | Polling loop active (interval=%ds)",
            self._settings.poll_interval_seconds,
        )

        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise  # propagate so stop() can await the task
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("ERROR | Unexpected error in scheduler tick: %s", exc)

            try:
                await asyncio.sleep(self._settings.poll_interval_seconds)
            except asyncio.CancelledError:
                raise

    async def _tick(self) -> None:
        """Execute one full poll-and-evaluate cycle inside a fresh DB session."""
        assert self._session_factory is not None, "Scheduler not started"

        # Step 1: Fetch latest candles
        candles = await self._market_service.fetch_latest_candles()

        if not candles:
            # Market data unavailable this tick — do nothing
            return

        # Step 2: Evaluate signals using a fresh session per tick
        signals = []
        async with self._session_factory() as session:
            signals = await self._signal_service.evaluate(candles, session)

        # Step 3: Broadcast real-time update to connected SSE dashboard clients
        try:
            from app.services.broadcaster import get_broadcaster
            from app.strategy.engine import IndicatorEngine

            broadcaster = get_broadcaster()
            latest_candle = candles[-1]
            engine = IndicatorEngine()
            vals = engine.calculate(candles)

            tick_payload = {
                "market": {
                    "symbol": self._settings.symbol,
                    "timeframe": self._settings.timeframe,
                    "price": latest_candle.close,
                    "timestamp": latest_candle.timestamp.isoformat(),
                },
                "indicators": {
                    "EMA9": vals.ema_fast,
                    "EMA21": vals.ema_slow,
                    "RSI": vals.rsi,
                    "ADX": vals.adx,
                    "DI+": vals.di_plus,
                    "DI-": vals.di_minus,
                    "SMA81": vals.sma_81,
                    "ATR": vals.atr,
                    "ema_fast": vals.ema_fast,
                    "ema_slow": vals.ema_slow,
                    "rsi": vals.rsi,
                    "adx": vals.adx,
                    "di_plus": vals.di_plus,
                    "di_minus": vals.di_minus,
                    "sma_81": vals.sma_81,
                    "atr": vals.atr,
                },
                "status": {
                    "system_status": "operational",
                    "market_data_status": "connected",
                    "database_status": "connected",
                    "telegram_status": (
                        "enabled"
                        if self._settings.telegram_enabled
                        and self._settings.telegram_bot_token
                        and self._settings.telegram_chat_id
                        else "disabled"
                    ),
                    "signal_engine_status": "running",
                    "last_market_update": latest_candle.timestamp.isoformat(),
                    "last_processed_candle": latest_candle.timestamp.isoformat(),
                },
            }

            if signals:
                latest_sig = signals[-1]
                tick_payload["current_signal"] = {
                    "signal": latest_sig.signal_type,
                    "source": latest_sig.signal_source,
                    "price": latest_sig.price,
                    "candle_time": latest_sig.candle_time.isoformat(),
                    "trend": latest_sig.trend,
                }
                tick_payload["new_signals"] = [
                    {
                        "id": s.id,
                        "symbol": s.symbol,
                        "timeframe": s.timeframe,
                        "signal_type": s.signal_type,
                        "signal_source": s.signal_source,
                        "candle_time": s.candle_time.isoformat(),
                        "price": s.price,
                        "rsi": s.rsi,
                        "adx": s.adx,
                        "trend": s.trend,
                        "telegram_sent": s.telegram_sent,
                        "telegram_attempts": s.telegram_attempts,
                    }
                    for s in signals
                ]

            await broadcaster.broadcast("tick", tick_payload)
        except Exception as exc:
            logger.debug("Broadcaster tick event skipped: %s", exc)
