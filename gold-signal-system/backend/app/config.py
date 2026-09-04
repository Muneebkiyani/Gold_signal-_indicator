"""
XAUUSD Gold Signal System — Application Configuration
======================================================
Centralized, typed settings loaded from environment variables / .env file.

Security rules enforced here:
  - Secrets (API keys, Telegram tokens) are NEVER logged or exposed.
  - Telegram credentials are NEVER sent to the frontend.
  - The .env file is NEVER committed (enforced via .gitignore).

Usage:
    from app.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ── Allowed literals ──────────────────────────────────────────────────────────
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


class Settings(BaseSettings):
    """
    All application settings.

    Variables are read (in priority order) from:
      1. Real environment variables
      2. .env file in the working directory
      3. Field defaults defined below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # DATA_PROVIDER_API_KEY == data_provider_api_key
        extra="ignore",         # silently ignore unknown env vars
        populate_by_name=True,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field("XAUUSD Gold Signal System", description="Human-readable application name")
    app_version: str = Field("1.0.0", description="Semantic version")
    debug: bool = Field(False, description="Enable debug mode (verbose logging)")
    log_level: str = Field("INFO", description="Logging level: DEBUG|INFO|WARNING|ERROR|CRITICAL")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field("0.0.0.0", description="Bind host for uvicorn")
    port: int = Field(8000, ge=1, le=65535, description="Bind port for uvicorn")

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as comma-separated string to avoid pydantic-settings trying to
    # JSON-decode a List[str] from the .env file on Python 3.9.
    allowed_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Return CORS allowed origins as a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        "sqlite+aiosqlite:///./data/signals.db",
        description="SQLAlchemy async database URL",
        alias="DATABASE_URL",
    )

    # ── Market Data Provider ──────────────────────────────────────────────────
    data_provider_api_key: str = Field(
        "",
        description="API key for the market data provider — KEEP SECRET",
        alias="DATA_PROVIDER_API_KEY",
    )
    data_provider_base_url: str = Field(
        "",
        description="Base URL of the market data REST API",
        alias="DATA_PROVIDER_BASE_URL",
    )

    # ── Telegram (NEVER exposed to frontend) ─────────────────────────────────
    telegram_bot_token: str = Field(
        "",
        description="Telegram Bot token — KEEP SECRET, never log or expose",
        alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_chat_id: str = Field(
        "",
        description="Telegram chat/channel ID to receive alerts",
        alias="TELEGRAM_CHAT_ID",
    )
    telegram_enabled: bool = Field(
        False,
        description="Enable Telegram alert dispatch",
    )
    no_entry_telegram_alerts: bool = Field(
        False,
        description="Suppress 'no entry' informational Telegram messages",
        alias="NO_ENTRY_TELEGRAM_ALERTS",
    )

    # ── Instrument ────────────────────────────────────────────────────────────
    symbol: str = Field(
        "XAUUSD",
        description="Trading symbol to monitor",
        alias="SYMBOL",
    )
    timeframe: str = Field(
        "M15",
        description="Chart timeframe: M1|M5|M15|M30|H1|H4|D1",
        alias="TIMEFRAME",
    )

    # ── EMA Settings ─────────────────────────────────────────────────────────
    ema_fast: int = Field(
        9,
        ge=1,
        le=500,
        description="Fast EMA period",
        alias="EMA_FAST",
    )
    ema_slow: int = Field(
        21,
        ge=1,
        le=500,
        description="Slow EMA period",
        alias="EMA_SLOW",
    )

    # ── RSI Settings ─────────────────────────────────────────────────────────
    rsi_length: int = Field(
        14,
        ge=2,
        le=500,
        description="RSI calculation period",
        alias="RSI_LENGTH",
    )
    rsi_mid: float = Field(
        50.0,
        ge=0.0,
        le=100.0,
        description="RSI midline (used for trend filtering)",
        alias="RSI_MID",
    )
    rsi_overbought: float = Field(
        70.0,
        ge=50.0,
        le=100.0,
        description="RSI overbought threshold",
        alias="RSI_OVERBOUGHT",
    )
    rsi_oversold: float = Field(
        30.0,
        ge=0.0,
        le=50.0,
        description="RSI oversold threshold",
        alias="RSI_OVERSOLD",
    )

    # ── ADX Settings ─────────────────────────────────────────────────────────
    adx_length: int = Field(
        14,
        ge=1,
        le=500,
        description="ADX DI calculation period",
        alias="ADX_LENGTH",
    )
    adx_smoothing: int = Field(
        14,
        ge=1,
        le=500,
        description="ADX smoothing period",
        alias="ADX_SMOOTHING",
    )
    adx_min: float = Field(
        20.0,
        ge=0.0,
        le=100.0,
        description="Minimum ADX value required to confirm trend strength",
        alias="ADX_MIN",
    )

    # ── SMA Settings ─────────────────────────────────────────────────────────
    sma_length: int = Field(
        81,
        ge=1,
        le=1000,
        description="Simple Moving Average period (trend bias filter)",
        alias="SMA_LENGTH",
    )

    # ── ATR Settings ─────────────────────────────────────────────────────────
    atr_length: int = Field(
        14,
        ge=1,
        le=500,
        description="Average True Range period (volatility / SL/TP sizing)",
        alias="ATR_LENGTH",
    )

    # ── Signal Behaviour ─────────────────────────────────────────────────────
    signal_on_close: bool = Field(
        True,
        description="Generate signals only on bar close (not mid-bar)",
        alias="SIGNAL_ON_CLOSE",
    )

    # ── Worker / Scheduler ────────────────────────────────────────────────────
    worker_enabled: bool = Field(
        True,
        description=(
            "Enable the background signal worker. "
            "Set to false to run the API without the polling loop."
        ),
        alias="WORKER_ENABLED",
    )
    poll_interval_seconds: int = Field(
        60,
        ge=10,
        le=3600,
        description=(
            "Seconds between market-data polls. "
            "M15 candles are 900 s; polling every 60 s is a reasonable default."
        ),
        alias="POLL_INTERVAL_SECONDS",
    )
    candle_history_limit: int = Field(
        150,
        ge=82,
        le=1000,
        description=(
            "Number of historical candles to load on startup for indicator warm-up. "
            "Must be >= 82 (SMA 81 requires 81 bars of history)."
        ),
        alias="CANDLE_HISTORY_LIMIT",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────────────────────────────────

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        upper = str(v).upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_LOG_LEVELS)}, got '{v}'"
            )
        return upper

    @field_validator("timeframe", mode="before")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        upper = str(v).upper()
        if upper not in _TIMEFRAMES:
            raise ValueError(
                f"timeframe must be one of {sorted(_TIMEFRAMES)}, got '{v}'"
            )
        return upper

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        cleaned = str(v).strip().upper()
        if not cleaned:
            raise ValueError("symbol must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_ema_ordering(self) -> "Settings":
        """Fast EMA period must be strictly less than slow EMA period."""
        if self.ema_fast >= self.ema_slow:
            raise ValueError(
                f"EMA_FAST ({self.ema_fast}) must be less than EMA_SLOW ({self.ema_slow})"
            )
        return self

    @model_validator(mode="after")
    def validate_rsi_band_ordering(self) -> "Settings":
        """RSI oversold must be strictly less than overbought."""
        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError(
                f"RSI_OVERSOLD ({self.rsi_oversold}) must be less than "
                f"RSI_OVERBOUGHT ({self.rsi_overbought})"
            )
        return self

    # ─────────────────────────────────────────────────────────────────────────
    # Safe representation — secrets are NEVER printed
    # ─────────────────────────────────────────────────────────────────────────

    def safe_dict(self) -> dict:
        """
        Return a copy of settings safe for logging.
        All secret fields are replaced with masked values.
        """
        _SECRETS = {"data_provider_api_key", "telegram_bot_token", "telegram_chat_id"}
        result = {}
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if field_name in _SECRETS:
                result[field_name] = "***" if value else "(not set)"
            else:
                result[field_name] = value
        return result

    def __repr__(self) -> str:
        """Never expose secrets in repr."""
        safe = self.safe_dict()
        pairs = ", ".join(f"{k}={v!r}" for k, v in safe.items())
        return f"Settings({pairs})"


# ── Singleton accessor ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    The cache is invalidated only on process restart.
    Use `get_settings.cache_clear()` in tests to reset between test cases.
    """
    return Settings()
