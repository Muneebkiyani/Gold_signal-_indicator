"""
Candle — OHLCV bar model.

Represents one price bar for a given symbol + timeframe.
Designed for SQLite today; PostgreSQL compatible (no SQLite-specific types used).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Candle(SQLModel, table=True):
    """
    One OHLCV price bar.

    The combination (symbol, timeframe, timestamp) is unique — a bar
    for XAUUSD M15 at 2024-01-01 08:00 UTC can only exist once.
    """

    __tablename__ = "candles"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "timestamp",
            name="uq_candle_bar",
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

    # ── Bar time ──────────────────────────────────────────────────────────────
    timestamp: datetime = Field(
        index=True,
        description="UTC open-time of the bar",
    )

    # ── OHLCV ─────────────────────────────────────────────────────────────────
    open: float = Field(description="Bar open price")
    high: float = Field(description="Bar high price")
    low: float = Field(description="Bar low price")
    close: float = Field(description="Bar close price")
    volume: float = Field(default=0.0, description="Bar volume (contracts / lots)")

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Row insertion timestamp (UTC)",
    )
