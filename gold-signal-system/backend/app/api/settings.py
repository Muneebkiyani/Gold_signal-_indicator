"""
Settings endpoints — GET /api/settings, PUT /api/settings
Provides sanitized configuration viewing and dynamic updates.
Ensures private keys, tokens, and credentials are never exposed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import SettingsResponse, UpdateSettingsRequest
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_settings_response(settings: Settings) -> SettingsResponse:
    """Extract strictly safe fields into SettingsResponse."""
    return SettingsResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        debug=settings.debug,
        log_level=settings.log_level,
        host=settings.host,
        port=settings.port,
        allowed_origins=settings.allowed_origins,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
        ema_fast=settings.ema_fast,
        ema_slow=settings.ema_slow,
        rsi_length=settings.rsi_length,
        rsi_mid=settings.rsi_mid,
        rsi_overbought=settings.rsi_overbought,
        rsi_oversold=settings.rsi_oversold,
        adx_length=settings.adx_length,
        adx_smoothing=settings.adx_smoothing,
        adx_min=settings.adx_min,
        sma_length=settings.sma_length,
        atr_length=settings.atr_length,
        signal_on_close=settings.signal_on_close,
        worker_enabled=settings.worker_enabled,
        poll_interval_seconds=settings.poll_interval_seconds,
        candle_history_limit=settings.candle_history_limit,
        telegram_enabled=settings.telegram_enabled,
        no_entry_telegram_alerts=settings.no_entry_telegram_alerts,
    )


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get System Settings",
    description="Returns sanitized system settings. Excludes all private credentials and tokens.",
)
async def get_system_settings() -> SettingsResponse:
    settings = get_settings()
    return _to_settings_response(settings)


@router.put(
    "/settings",
    response_model=SettingsResponse,
    summary="Update System Settings",
    description="Updates configurable system settings with validation.",
)
async def update_system_settings(
    payload: UpdateSettingsRequest,
) -> SettingsResponse:
    settings = get_settings()
    update_data = payload.model_dump(exclude_unset=True)

    # 1. Validation for EMA fast/slow ordering
    target_ema_fast = update_data.get("ema_fast", settings.ema_fast)
    target_ema_slow = update_data.get("ema_slow", settings.ema_slow)
    if target_ema_fast >= target_ema_slow:
        raise HTTPException(
            status_code=422,
            detail=f"EMA fast ({target_ema_fast}) must be less than EMA slow ({target_ema_slow})",
        )

    # 2. Validation for RSI oversold/overbought ordering
    target_rsi_os = update_data.get("rsi_oversold", settings.rsi_oversold)
    target_rsi_ob = update_data.get("rsi_overbought", settings.rsi_overbought)
    if target_rsi_os >= target_rsi_ob:
        raise HTTPException(
            status_code=422,
            detail=(
                f"RSI oversold ({target_rsi_os}) must be less than "
                f"overbought ({target_rsi_ob})"
            ),
        )

    # 3. Apply updates to the current settings singleton
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
            logger.info("SETTINGS UPDATED | %s = %s", key, value)

    return _to_settings_response(settings)
