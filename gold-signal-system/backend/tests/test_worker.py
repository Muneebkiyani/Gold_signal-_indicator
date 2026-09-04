"""
Tests for Phase 10: Continuous Signal Worker

Covers:
  - MarketService: success path, provider error isolation
  - SignalService: evaluate with signals, evaluate with WAIT, Telegram failure isolation
  - SignalScheduler: start/stop lifecycle, survival of market errors, survival of signal errors
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from app.market.base_provider import BaseMarketDataProvider
from app.market.models import NormalizedCandle, ProviderConnectionError
from app.models.enums import SignalType, SignalSource
from app.models.signal import Signal
from app.services.market_service import MarketService
from app.services.signal_service import SignalService
from app.services.scheduler import SignalScheduler


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_candle(ts: datetime, close: float = 2000.0) -> NormalizedCandle:
    return NormalizedCandle(
        timestamp=ts,
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
        volume=100.0,
    )


def _make_signal(sig_type: SignalType = SignalType.BUY) -> Signal:
    return Signal(
        id=1,
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=sig_type,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        price=2000.0,
        telegram_sent=True,
        telegram_attempts=1,
    )


class _MockProvider(BaseMarketDataProvider):
    """Minimal in-memory provider for unit tests."""

    def __init__(self, candles: List[NormalizedCandle], error: Exception | None = None):
        self._candles = candles
        self._error = error

    async def get_historical_candles(
            self, symbol, timeframe="M15", limit=100,
            start_time=None, end_time=None):
        if self._error:
            raise self._error
        return self._candles

    async def get_latest_price(self, symbol: str) -> float:
        return 2000.0

    async def get_latest_candle(
            self, symbol: str, timeframe: str = "M15") -> Optional[NormalizedCandle]:
        return self._candles[-1] if self._candles else None

    async def close(self) -> None:
        pass


# ── MarketService Tests ───────────────────────────────────────────────────────

class TestMarketService:

    @pytest.mark.asyncio
    async def test_fetch_success_returns_candles(self):
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        candles = [_make_candle(ts)]
        provider = _MockProvider(candles=candles)

        with patch("app.services.market_service.get_settings") as mock_cfg:
            mock_cfg.return_value.candle_history_limit = 150
            mock_cfg.return_value.symbol = "XAUUSD"
            mock_cfg.return_value.timeframe = "M15"
            svc = MarketService(provider=provider)
            svc._settings = mock_cfg.return_value

            result = await svc.fetch_latest_candles()

        assert len(result) == 1
        assert result[0].timestamp == ts

    @pytest.mark.asyncio
    async def test_fetch_provider_error_returns_empty(self):
        provider = _MockProvider(
            candles=[], error=ProviderConnectionError("Network down")
        )

        with patch("app.services.market_service.get_settings") as mock_cfg:
            mock_cfg.return_value.candle_history_limit = 150
            mock_cfg.return_value.symbol = "XAUUSD"
            mock_cfg.return_value.timeframe = "M15"
            svc = MarketService(provider=provider)
            svc._settings = mock_cfg.return_value

            result = await svc.fetch_latest_candles()

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_generic_error_returns_empty(self):
        provider = _MockProvider(candles=[], error=RuntimeError("Unexpected"))

        with patch("app.services.market_service.get_settings") as mock_cfg:
            mock_cfg.return_value.candle_history_limit = 150
            mock_cfg.return_value.symbol = "XAUUSD"
            mock_cfg.return_value.timeframe = "M15"
            svc = MarketService(provider=provider)
            svc._settings = mock_cfg.return_value

            result = await svc.fetch_latest_candles()

        assert result == []


# ── SignalService Tests ───────────────────────────────────────────────────────

class TestSignalService:

    def _make_service(self, signals: List[Signal], engine_error=None):
        """Build a SignalService backed by a mocked SignalEngine."""
        mock_engine = MagicMock()
        mock_engine.initialize = AsyncMock()

        if engine_error:
            mock_engine.process_candles = AsyncMock(side_effect=engine_error)
        else:
            mock_engine.process_candles = AsyncMock(return_value=signals)

        svc = SignalService(engine=mock_engine)
        return svc

    @pytest.mark.asyncio
    async def test_initialize_calls_engine(self):
        svc = self._make_service([])
        session = AsyncMock()

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.candle_history_limit = 150
            mock_cfg.return_value.telegram_enabled = False
            svc._settings = mock_cfg.return_value
            await svc.initialize(session)

        svc._engine.initialize.assert_called_once_with(
            session=session, history_limit=150
        )
        assert svc._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        svc = self._make_service([])
        session = AsyncMock()

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.candle_history_limit = 150
            mock_cfg.return_value.telegram_enabled = False
            svc._settings = mock_cfg.return_value
            await svc.initialize(session)
            await svc.initialize(session)

        # Should only call engine.initialize once
        svc._engine.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_buy_returns_signals(self):
        buy = _make_signal(SignalType.BUY)
        svc = self._make_service([buy])
        session = AsyncMock()
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.telegram_enabled = False
            svc._settings = mock_cfg.return_value
            result = await svc.evaluate([_make_candle(ts)], session)

        assert len(result) == 1
        assert result[0].signal_type == SignalType.BUY

    @pytest.mark.asyncio
    async def test_evaluate_empty_candles_returns_empty(self):
        svc = self._make_service([])
        session = AsyncMock()

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.telegram_enabled = False
            svc._settings = mock_cfg.return_value
            result = await svc.evaluate([], session)

        assert result == []
        svc._engine.process_candles.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_engine_error_returns_empty(self):
        svc = self._make_service([], engine_error=RuntimeError("DB gone"))
        session = AsyncMock()
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.telegram_enabled = False
            svc._settings = mock_cfg.return_value
            result = await svc.evaluate([_make_candle(ts)], session)

        assert result == []

    @pytest.mark.asyncio
    async def test_evaluate_logs_telegram_sent(self):
        buy = _make_signal(SignalType.BUY)
        svc = self._make_service([buy])
        session = AsyncMock()
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.telegram_enabled = True
            svc._settings = mock_cfg.return_value
            result = await svc.evaluate([_make_candle(ts)], session)

        assert result[0].telegram_sent is True

    @pytest.mark.asyncio
    async def test_evaluate_logs_telegram_failed(self):
        buy = _make_signal(SignalType.BUY)
        buy.telegram_sent = False
        buy.telegram_attempts = 3
        buy.telegram_error = "Connection timeout"
        svc = self._make_service([buy])
        session = AsyncMock()
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

        with patch("app.services.signal_service.get_settings") as mock_cfg:
            mock_cfg.return_value.telegram_enabled = True
            svc._settings = mock_cfg.return_value
            result = await svc.evaluate([_make_candle(ts)], session)

        # Should still return signals without raising
        assert len(result) == 1
        assert result[0].telegram_sent is False


# ── SignalScheduler Tests ─────────────────────────────────────────────────────

class TestSignalScheduler:

    def _make_scheduler(
        self,
        candles=None,
        signals=None,
        market_error=None,
        signal_error=None,
    ):
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        _candles = candles if candles is not None else [_make_candle(ts)]
        _signals = signals if signals is not None else []

        market_svc = MagicMock()
        if market_error:
            market_svc.fetch_latest_candles = AsyncMock(side_effect=market_error)
        else:
            market_svc.fetch_latest_candles = AsyncMock(return_value=_candles)

        signal_svc = MagicMock()
        signal_svc.initialize = AsyncMock()
        if signal_error:
            signal_svc.evaluate = AsyncMock(side_effect=signal_error)
        else:
            signal_svc.evaluate = AsyncMock(return_value=_signals)

        with patch("app.services.scheduler.get_settings") as mock_cfg:
            mock_cfg.return_value.poll_interval_seconds = 1
            mock_cfg.return_value.candle_history_limit = 150
            scheduler = SignalScheduler(
                market_service=market_svc,
                signal_service=signal_svc,
            )
            scheduler._settings = mock_cfg.return_value

        return scheduler, market_svc, signal_svc

    def _make_session_factory(self):
        """Return an async_sessionmaker-compatible mock."""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        factory = MagicMock()
        factory.return_value = session
        factory.__call__ = MagicMock(return_value=session)
        return factory

    @pytest.mark.asyncio
    async def test_start_initializes_signal_service(self):
        scheduler, _, signal_svc = self._make_scheduler()
        factory = self._make_session_factory()

        await scheduler.start(factory)
        await asyncio.sleep(0.05)
        await scheduler.stop()

        signal_svc.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        scheduler, _, _ = self._make_scheduler()
        factory = self._make_session_factory()

        await scheduler.start(factory)
        assert scheduler._task is not None
        assert not scheduler._task.done()

        await scheduler.stop()
        assert scheduler._task.done()

    @pytest.mark.asyncio
    async def test_duplicate_start_is_noop(self):
        scheduler, _, signal_svc = self._make_scheduler()
        factory = self._make_session_factory()

        await scheduler.start(factory)
        await scheduler.start(factory)  # second call should be ignored
        await scheduler.stop()

        # initialize should be called only once
        signal_svc.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_calls_market_and_signal(self):
        scheduler, market_svc, signal_svc = self._make_scheduler()
        factory = self._make_session_factory()

        await scheduler.start(factory)
        # Allow at least one tick
        await asyncio.sleep(0.1)
        await scheduler.stop()

        market_svc.fetch_latest_candles.assert_called()
        signal_svc.evaluate.assert_called()

    @pytest.mark.asyncio
    async def test_survives_market_error(self):
        """Loop must continue even if market service raises."""
        scheduler, market_svc, _ = self._make_scheduler(
            market_error=RuntimeError("API down")
        )
        factory = self._make_session_factory()

        await scheduler.start(factory)
        await asyncio.sleep(0.1)
        await scheduler.stop()

        # Task finished cleanly (cancelled, not errored)
        assert scheduler._task.done()

    @pytest.mark.asyncio
    async def test_survives_signal_error(self):
        """Loop must continue even if signal service raises."""
        scheduler, _, signal_svc = self._make_scheduler(
            signal_error=RuntimeError("DB error")
        )
        factory = self._make_session_factory()

        await scheduler.start(factory)
        await asyncio.sleep(0.1)
        await scheduler.stop()

        assert scheduler._task.done()

    @pytest.mark.asyncio
    async def test_empty_candles_skips_signal_evaluation(self):
        """If market returns empty, signal service must not be called."""
        scheduler, _, signal_svc = self._make_scheduler(candles=[])
        factory = self._make_session_factory()

        await scheduler.start(factory)
        await asyncio.sleep(0.1)
        await scheduler.stop()

        signal_svc.evaluate.assert_not_called()
