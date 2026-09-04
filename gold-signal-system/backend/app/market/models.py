"""
Market data models, exceptions, and candle normalization utilities.

Every market data provider must produce NormalizedCandle instances.
All timestamps are strictly stored in UTC with deterministic boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Exceptions ───────────────────────────────────────────────────────────────

class MarketDataError(Exception):
    """Base exception for all market data errors."""


class ProviderConnectionError(MarketDataError):
    """Raised when failing to connect to the market data provider (network error)."""


class ProviderTimeoutError(MarketDataError):
    """Raised when a market data request times out."""


class ProviderResponseError(MarketDataError):
    """Raised when the provider returns an HTTP error or API error status."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class MalformedDataError(MarketDataError):
    """Raised when provider response data is malformed or cannot be parsed."""


# ─── Candle Boundary Helpers ─────────────────────────────────────────────────

def align_to_m15_boundary(dt: datetime) -> datetime:
    """
    Deterministically align a datetime to the 15-minute candle open boundary.
    e.g. 10:14:32 -> 10:00:00, 10:29:59 -> 10:15:00, 10:45:01 -> 10:45:00.
    Always returns a timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    minute_bucket = (dt.minute // 15) * 15
    return dt.replace(minute=minute_bucket, second=0, microsecond=0)


def align_to_boundary(dt: datetime, timeframe: str = "M15") -> datetime:
    """
    Deterministically align a datetime to the open boundary of the given timeframe.
    Supported timeframes: M1, M5, M15, M30, H1, H4, D1.
    Always returns a timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    tf = timeframe.upper()
    if tf == "M1":
        return dt.replace(second=0, microsecond=0)
    elif tf == "M5":
        return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
    elif tf == "M15":
        return align_to_m15_boundary(dt)
    elif tf == "M30":
        return dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
    elif tf == "H1":
        return dt.replace(minute=0, second=0, microsecond=0)
    elif tf == "H4":
        return dt.replace(hour=(dt.hour // 4) * 4, minute=0, second=0, microsecond=0)
    elif tf == "D1":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(second=0, microsecond=0)


# ─── Normalized Candle Model ─────────────────────────────────────────────────

class NormalizedCandle(BaseModel):
    """
    Normalized OHLCV candle representation.

    All market data providers must convert their proprietary responses into this format.
    Guarantees:
      - timestamp is always UTC timezone-aware
      - numeric fields (open, high, low, close, volume) are floats
      - high >= max(open, close) and low <= min(open, close) sanity checks
    """
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    timestamp: datetime = Field(description="Deterministic UTC open timestamp of the candle")
    open: float = Field(description="Open price")
    high: float = Field(description="Highest price")
    low: float = Field(description="Lowest price")
    close: float = Field(description="Close price")
    volume: float = Field(default=0.0, ge=0.0, description="Trading volume")

    @classmethod
    def create(
        cls,
        timestamp: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float = 0.0,
        timeframe: str = "M15",
    ) -> NormalizedCandle:
        """
        Factory method that ensures deterministic boundary alignment and UTC conversion.
        """
        aligned_ts = align_to_boundary(timestamp, timeframe)
        return cls(
            timestamp=aligned_ts,
            open=float(open),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=max(0.0, float(volume)),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary with ISO-formatted timestamp."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
