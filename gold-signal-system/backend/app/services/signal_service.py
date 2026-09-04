"""
Signal Service — fault-isolated wrapper around SignalEngine.

Responsibilities:
  - Initialize SignalEngine from the database on startup.
  - Run one evaluation cycle per set of incoming candles.
  - Emit structured log lines (NEW CANDLE, SIGNAL CHECK, BUY/SELL DETECTED,
    TELEGRAM SENT / FAILED).
  - Swallow all Telegram errors so a failed alert never aborts a tick.

This module does NOT raise exceptions out of ``evaluate()``.
"""

from __future__ import annotations

import logging
from typing import List, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.market.models import NormalizedCandle
from app.models.enums import SignalType
from app.models.signal import Signal
from app.services.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class SignalService:
    """
    Wraps ``SignalEngine`` with structured logging and error isolation.

    Usage::

        svc = SignalService()
        await svc.initialize(session)        # once on startup
        signals = await svc.evaluate(candles, session)   # each tick
    """

    def __init__(self, engine: SignalEngine | None = None) -> None:
        self._settings = get_settings()
        self._engine = engine or SignalEngine()
        self._initialized = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self, session: AsyncSession) -> None:
        """
        Load historical state from the database to warm up indicators
        and restore ``last_evaluated_candle_time``.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._initialized:
            return
        await self._engine.initialize(
            session=session,
            history_limit=self._settings.candle_history_limit,
        )
        self._initialized = True

    # ── Evaluation ────────────────────────────────────────────────────────────

    async def evaluate(
        self,
        candles: Sequence[NormalizedCandle],
        session: AsyncSession,
    ) -> List[Signal]:
        """
        Feed *candles* through the full pipeline:

          CandleManager → IndicatorEngine → Strategy → DB → Telegram

        Returns the list of newly persisted signals (may be empty).
        Never raises.
        """
        if not candles:
            return []

        logger.info("SIGNAL CHECK | Evaluating %d incoming candle(s)", len(candles))

        try:
            signals = await self._engine.process_candles(
                candles=list(candles),
                session=session,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("ERROR | Signal evaluation failed: %s", exc)
            return []

        for sig in signals:
            candle_ts = sig.candle_time.isoformat() if sig.candle_time else "unknown"
            logger.info(
                "NEW CANDLE | %s %s bar=%s",
                sig.symbol,
                sig.timeframe,
                candle_ts,
            )

            if sig.signal_type in (SignalType.BUY, SignalType.SELL, "BUY", "SELL"):
                logger.info(
                    "%s DETECTED | source=%s price=%.2f bar=%s",
                    sig.signal_type,
                    sig.signal_source or "unknown",
                    sig.price or 0.0,
                    candle_ts,
                )

            # Telegram outcome is already reflected on the signal by SignalEngine.
            # Log the result here for the structured log contract.
            if self._settings.telegram_enabled:
                if sig.telegram_sent:
                    logger.info(
                        "TELEGRAM SENT | signal_id=%s type=%s",
                        sig.id,
                        sig.signal_type,
                    )
                elif sig.telegram_attempts and sig.telegram_attempts > 0:
                    logger.warning(
                        "TELEGRAM FAILED | signal_id=%s attempts=%d error=%s",
                        sig.id,
                        sig.telegram_attempts,
                        sig.telegram_error,
                    )

        return signals
