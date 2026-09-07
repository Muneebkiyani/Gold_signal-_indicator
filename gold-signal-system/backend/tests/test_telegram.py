"""
Tests for Telegram alert service.

Covers:
  - Message formatting for all signal types (EMA BUY/SELL, SMA BUY/SELL)
  - WAIT and NO_ENTRY suppression logic
  - send_message success and bounded retry-on-failure
  - test_connection success and failure
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.telegram import TelegramService
from app.models.signal import Signal
from app.models.enums import SignalType, SignalSource


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def telegram_service():
    """TelegramService with mocked settings (no real credentials)."""
    with patch("app.services.telegram.get_settings") as mock_get:
        cfg = MagicMock()
        cfg.telegram_bot_token = "TEST_TOKEN"
        cfg.telegram_chat_id = "TEST_CHAT"
        cfg.no_entry_telegram_alerts = False
        mock_get.return_value = cfg
        svc = TelegramService()
        svc.settings = cfg
        yield svc


@pytest.fixture
def ema_buy_signal():
    return Signal(
        id=1,
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        price=2000.50,
        ema_fast=2000.10,
        ema_slow=1995.00,
        rsi=65.5,
        adx=30.2,
        di_plus=25.1,
        di_minus=15.0,
        sma_81=1990.00,
        atr=5.5,
        trend="BULLISH",
    )


@pytest.fixture
def ema_sell_signal():
    return Signal(
        id=2,
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.SELL,
        signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        price=2001.00,
        ema_fast=1995.00,
        ema_slow=2000.00,
        rsi=35.0,
        adx=28.0,
        di_plus=12.0,
        di_minus=22.0,
        sma_81=1990.00,
        atr=4.5,
        trend="BEARISH",
    )


@pytest.fixture
def sma_buy_signal():
    return Signal(
        id=3,
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.BUY,
        signal_source=SignalSource.SMA_81,
        candle_time=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        price=1980.50,
        sma_81=1975.00,
    )


@pytest.fixture
def sma_sell_signal():
    return Signal(
        id=4,
        symbol="XAUUSD",
        timeframe="M15",
        signal_type=SignalType.SELL,
        signal_source=SignalSource.SMA_81,
        candle_time=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        price=1980.50,
        sma_81=1985.00,
    )


# ── Formatting tests ──────────────────────────────────────────────────────────

def test_format_ema_buy(telegram_service, ema_buy_signal):
    text = telegram_service.format_signal(ema_buy_signal)
    assert text is not None
    assert "🟢 XAUUSD BUY SIGNAL" in text
    assert "System: EMA + RSI + ADX" in text
    assert "Price: 2000.5" in text
    assert "EMA 9: 2000.1" in text
    assert "RSI: 65.5" in text
    assert "ADX: 30.2" in text
    assert "Trend: BULLISH" in text


def test_format_ema_sell(telegram_service, ema_sell_signal):
    text = telegram_service.format_signal(ema_sell_signal)
    assert text is not None
    assert "🔴 XAUUSD SELL SIGNAL" in text
    assert "System: EMA + RSI + ADX" in text
    assert "RSI: 35.0" in text
    assert "Trend: BEARISH" in text


def test_format_sma_buy(telegram_service, sma_buy_signal):
    text = telegram_service.format_signal(sma_buy_signal)
    assert text is not None
    assert "🟢 XAUUSD SMA BUY" in text
    assert "System: SMA 81" in text
    assert "Price crossed ABOVE SMA 81." in text
    assert "Price: 1980.5" in text
    assert "SMA 81: 1975.0" in text


def test_format_sma_sell(telegram_service, sma_sell_signal):
    text = telegram_service.format_signal(sma_sell_signal)
    assert text is not None
    assert "🔴 XAUUSD SMA SELL" in text
    assert "Price crossed BELOW SMA 81." in text
    assert "SMA 81: 1985.0" in text


def test_format_wait_returns_none(telegram_service):
    sig = Signal(
        id=5, symbol="XAUUSD", timeframe="M15",
        signal_type=SignalType.WAIT, signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc), price=2000.0,
    )
    assert telegram_service.format_signal(sig) is None


def test_format_no_entry_suppressed_by_default(telegram_service):
    sig = Signal(
        id=6, symbol="XAUUSD", timeframe="M15",
        signal_type=SignalType.NO_ENTRY, signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc), price=2000.0,
    )
    # default: no_entry_telegram_alerts = False
    assert telegram_service.format_signal(sig) is None


def test_format_no_entry_allowed_when_enabled(telegram_service):
    telegram_service.settings.no_entry_telegram_alerts = True
    sig = Signal(
        id=7, symbol="XAUUSD", timeframe="M15",
        signal_type=SignalType.NO_ENTRY, signal_source=SignalSource.EMA_RSI_ADX,
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc), price=2000.0,
    )
    # NO_ENTRY passes the suppression gate but has no matching format branch,
    # so it returns None — callers must add a branch if a message is desired.
    result = telegram_service.format_signal(sig)
    assert result is None  # no EMA_RSI_ADX branch for NO_ENTRY yet


# ── HTTP dispatch tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_success(telegram_service):
    """send_message returns (True, None) when _sync_telegram_request succeeds."""
    mock_result = {"ok": True, "result": {"message_id": 42}}
    with patch(
        "app.services.telegram._sync_telegram_request",
        return_value=mock_result,
    ) as mock_req:
        success, error = await telegram_service.send_message("Hello")

        assert success is True
        assert error is None
        mock_req.assert_called_once()
        # Verify call args: token, endpoint, payload
        args = mock_req.call_args[0]
        assert args[1] == "sendMessage"
        assert args[2]["text"] == "Hello"
        assert args[2]["chat_id"] == "TEST_CHAT"


@pytest.mark.asyncio
async def test_send_message_retries_then_fails(telegram_service):
    """send_message retries 3× and returns (False, error) on persistent failure."""
    with patch(
        "app.services.telegram._sync_telegram_request",
        side_effect=OSError("Network Error"),
    ) as mock_req:
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            success, error = await telegram_service.send_message("Hello")

            assert success is False
            assert "Network Error" in error
            # 3 total attempts
            assert mock_req.call_count == 3
            # 2 sleeps (between attempt 1→2 and 2→3)
            assert mock_sleep.call_count == 2


# ── Connectivity tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_success(telegram_service):
    """test_connection returns True when the bot token is valid."""
    mock_result = {"ok": True, "result": {"username": "goldbot"}}
    with patch(
        "app.services.telegram._sync_telegram_request",
        return_value=mock_result,
    ):
        result = await telegram_service.test_connection()
        assert result is True


@pytest.mark.asyncio
async def test_connection_failure(telegram_service):
    """test_connection returns False when _sync_telegram_request raises."""
    with patch(
        "app.services.telegram._sync_telegram_request",
        side_effect=OSError("401 Unauthorized"),
    ):
        result = await telegram_service.test_connection()
        assert result is False


@pytest.mark.asyncio
async def test_connection_no_token(telegram_service):
    telegram_service.settings.telegram_bot_token = ""
    result = await telegram_service.test_connection()
    assert result is False
