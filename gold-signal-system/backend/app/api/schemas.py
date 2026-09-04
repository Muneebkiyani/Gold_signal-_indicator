"""
Pydantic schemas for the FastAPI API endpoints.
Provides response models and request validation for dashboard integration.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StatusResponse(BaseModel):
    """System health and operational status."""

    system_status: str = Field(..., description="Overall system status (e.g. operational)")
    market_data_status: str = Field(..., description="Market data provider status")
    database_status: str = Field(..., description="Database connectivity status")
    telegram_status: str = Field(..., description="Telegram bot alert status")
    signal_engine_status: str = Field(..., description="Signal engine / scheduler status")
    last_market_update: Optional[datetime] = Field(
        None, description="UTC timestamp of the latest market data update"
    )
    last_processed_candle: Optional[datetime] = Field(
        None, description="UTC timestamp of the latest processed candle"
    )


class MarketResponse(BaseModel):
    """Latest market quote / candle data."""

    symbol: str = Field(..., description="Trading instrument symbol (e.g. XAUUSD)")
    timeframe: str = Field(..., description="Bar timeframe (e.g. M15)")
    price: Optional[float] = Field(None, description="Latest price or candle close")
    timestamp: Optional[datetime] = Field(
        None, description="Timestamp of the latest quote or candle bar"
    )


class IndicatorsResponse(BaseModel):
    """
    Technical indicators calculated for the latest candle.
    Supports both uppercase/alias notation (EMA9, DI+, etc.) and snake_case properties.
    """

    model_config = ConfigDict(populate_by_name=True)

    EMA9: Optional[float] = Field(None, description="EMA 9 period")
    EMA21: Optional[float] = Field(None, description="EMA 21 period")
    RSI: Optional[float] = Field(None, description="RSI 14 period")
    ADX: Optional[float] = Field(None, description="ADX 14 period")
    DI_plus: Optional[float] = Field(
        None, alias="DI+", serialization_alias="DI+", description="+DI 14 period"
    )
    DI_minus: Optional[float] = Field(
        None, alias="DI-", serialization_alias="DI-", description="-DI 14 period"
    )
    SMA81: Optional[float] = Field(None, description="SMA 81 period")
    ATR: Optional[float] = Field(None, description="ATR 14 period")

    # Snake_case compatibility aliases
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    sma_81: Optional[float] = None
    atr: Optional[float] = None


class SignalCurrentResponse(BaseModel):
    """Current active signal evaluation status."""

    signal: str = Field(..., description="Signal status: BUY | SELL | NO_ENTRY | WAIT")
    source: Optional[str] = Field(
        None, description="Strategy rule source: EMA_RSI_ADX | SMA_81 | None"
    )
    price: Optional[float] = Field(None, description="Price at signal generation")
    candle_time: Optional[datetime] = Field(
        None, description="UTC open-time of the bar that generated the signal"
    )
    trend: Optional[str] = Field(None, description="Market trend: UP | DOWN | FLAT")


class SignalResponse(BaseModel):
    """Persisted signal event record."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    symbol: str
    timeframe: str
    signal_type: str
    signal_source: str
    candle_time: datetime
    price: float
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    sma_81: Optional[float] = None
    atr: Optional[float] = None
    trend: Optional[str] = None
    telegram_sent: bool = False
    telegram_attempts: int = 0
    telegram_last_attempt: Optional[datetime] = None
    telegram_error: Optional[str] = None
    created_at: Optional[datetime] = None


class SignalListResponse(BaseModel):
    """Paginated collection of signals."""

    items: List[SignalResponse]
    total: int
    limit: int
    offset: int


class SettingsResponse(BaseModel):
    """
    Sanitized system configuration view.
    Private credentials and tokens are strictly excluded.
    """

    app_name: str
    app_version: str
    debug: bool
    log_level: str
    host: str
    port: int
    allowed_origins: str
    symbol: str
    timeframe: str
    ema_fast: int
    ema_slow: int
    rsi_length: int
    rsi_mid: float
    rsi_overbought: float
    rsi_oversold: float
    adx_length: int
    adx_smoothing: int
    adx_min: float
    sma_length: int
    atr_length: int
    signal_on_close: bool
    worker_enabled: bool
    poll_interval_seconds: int
    candle_history_limit: int
    telegram_enabled: bool
    no_entry_telegram_alerts: bool


class UpdateSettingsRequest(BaseModel):
    """Editable system settings payload."""

    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    ema_fast: Optional[int] = Field(None, ge=1, le=500)
    ema_slow: Optional[int] = Field(None, ge=1, le=500)
    rsi_length: Optional[int] = Field(None, ge=2, le=500)
    rsi_mid: Optional[float] = Field(None, ge=0.0, le=100.0)
    rsi_overbought: Optional[float] = Field(None, ge=50.0, le=100.0)
    rsi_oversold: Optional[float] = Field(None, ge=0.0, le=50.0)
    adx_length: Optional[int] = Field(None, ge=1, le=500)
    adx_smoothing: Optional[int] = Field(None, ge=1, le=500)
    adx_min: Optional[float] = Field(None, ge=0.0, le=100.0)
    sma_length: Optional[int] = Field(None, ge=1, le=1000)
    atr_length: Optional[int] = Field(None, ge=1, le=500)
    poll_interval_seconds: Optional[int] = Field(None, ge=10, le=3600)
    candle_history_limit: Optional[int] = Field(None, ge=82, le=1000)
    telegram_enabled: Optional[bool] = None
    no_entry_telegram_alerts: Optional[bool] = None
    worker_enabled: Optional[bool] = None
