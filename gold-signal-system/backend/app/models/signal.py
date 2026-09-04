"""
Signal — trading signal model.

Each row records one signal event produced by the strategy engine.
Includes all indicator values at the moment of signal generation,
plus Telegram dispatch metadata.

Unique constraint:
    (symbol, timeframe, candle_time, signal_source, signal_type)
    → the same signal cannot be inserted twice for the same bar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Signal(SQLModel, table=True):
    """
    One signal event produced by the strategy engine.

    The composite unique constraint
        (symbol, timeframe, candle_time, signal_source, signal_type)
    prevents duplicate alerts for the same bar.
    """

    __tablename__ = "signals"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "candle_time",
            "signal_source",
            "signal_type",
            name="uq_signal_bar",
        ),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Instrument ────────────────────────────────────────────────────────────
    symbol: str = Field(
        max_length=20,
        index=True,
        description="Trading symbol, e.g. XAUUSD",
    )
    timeframe: str = Field(
        max_length=10,
        index=True,
        description="Bar timeframe, e.g. M15",
    )

    # ── Signal metadata ───────────────────────────────────────────────────────
    signal_type: str = Field(
        max_length=20,
        index=True,
        description="Signal type: WAIT | BUY | SELL | NO_ENTRY",
    )
    signal_source: str = Field(
        max_length=30,
        index=True,
        description="Strategy rule: EMA_RSI_ADX | SMA_81",
    )

    # ── Bar reference ─────────────────────────────────────────────────────────
    candle_time: datetime = Field(
        index=True,
        description="UTC open-time of the bar that triggered the signal",
    )
    price: float = Field(
        description="Close price of the signal bar",
    )

    # ── Indicator snapshot ────────────────────────────────────────────────────
    # All values are Optional — not every strategy rule uses every indicator.
    ema_fast: Optional[float] = Field(default=None, description="Fast EMA value at signal bar")
    ema_slow: Optional[float] = Field(default=None, description="Slow EMA value at signal bar")
    rsi: Optional[float] = Field(default=None, description="RSI value at signal bar")
    adx: Optional[float] = Field(default=None, description="ADX value at signal bar")
    di_plus: Optional[float] = Field(default=None, description="+DI value at signal bar")
    di_minus: Optional[float] = Field(default=None, description="-DI value at signal bar")
    sma_81: Optional[float] = Field(default=None, description="SMA-81 value at signal bar")
    atr: Optional[float] = Field(default=None, description="ATR value at signal bar")
    trend: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Trend direction at signal time: UP | DOWN | FLAT",
    )

    # ── Telegram dispatch metadata ────────────────────────────────────────────
    telegram_sent: bool = Field(
        default=False,
        description="True once the Telegram alert is delivered successfully",
    )
    telegram_attempts: int = Field(
        default=0,
        description="Number of Telegram send attempts made",
    )
    telegram_last_attempt: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of the last Telegram send attempt",
    )
    telegram_error: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Last Telegram error message (if any)",
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Row insertion timestamp (UTC)",
    )
