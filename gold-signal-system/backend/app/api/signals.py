"""
Signals endpoints — GET /api/signal, GET /api/signals, GET /api/signals/latest
Provides queryable access to generated trading signals and recent history.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    SignalCurrentResponse,
    SignalListResponse,
    SignalResponse,
)
from app.config import get_settings
from app.crud.candle import get_latest_candle
from app.crud.signal import (
    count_signals,
    get_latest_signal,
    get_signals,
)
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/signal",
    response_model=SignalCurrentResponse,
    summary="Current Active Signal",
    description=(
        "Returns current active signal state (BUY, SELL, NO_ENTRY, WAIT), "
        "source, and trend."
    ),
)
async def get_current_signal(
    session: AsyncSession = Depends(get_db),
) -> SignalCurrentResponse:
    settings = get_settings()

    # Retrieve latest signal from database
    latest_sig = await get_latest_signal(
        session=session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
    )

    if latest_sig is not None:
        return SignalCurrentResponse(
            signal=latest_sig.signal_type,
            source=latest_sig.signal_source,
            price=latest_sig.price,
            candle_time=latest_sig.candle_time,
            trend=latest_sig.trend,
        )

    # Fallback to latest candle if no signal generated yet
    latest_candle = await get_latest_candle(
        session=session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
    )

    if latest_candle is not None:
        return SignalCurrentResponse(
            signal="WAIT",
            source=None,
            price=latest_candle.close,
            candle_time=latest_candle.timestamp,
            trend="FLAT",
        )

    return SignalCurrentResponse(
        signal="WAIT",
        source=None,
        price=None,
        candle_time=None,
        trend="FLAT",
    )


@router.get(
    "/signals/latest",
    response_model=SignalResponse,
    summary="Latest Persisted Signal Record",
    description="Returns the single most recent persisted signal event record.",
)
async def get_latest_signal_record(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
) -> SignalResponse:
    settings = get_settings()
    target_symbol = symbol or settings.symbol
    target_timeframe = timeframe or settings.timeframe

    latest = await get_latest_signal(
        session=session,
        symbol=target_symbol,
        timeframe=target_timeframe,
    )

    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No signals found for {target_symbol} {target_timeframe}",
        )

    return SignalResponse.model_validate(latest)


@router.get(
    "/signals",
    response_model=SignalListResponse,
    summary="Query Signal History",
    description="Query historical signals with pagination, limit, offset, and filters.",
)
async def list_signals(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of signals to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type: BUY, SELL, etc."),
    signal_source: Optional[str] = Query(None, description="Filter by strategy source"),
    session: AsyncSession = Depends(get_db),
) -> SignalListResponse:
    items = await get_signals(
        session=session,
        symbol=symbol,
        timeframe=timeframe,
        signal_type=signal_type,
        signal_source=signal_source,
        limit=limit,
        offset=offset,
    )

    total = await count_signals(
        session=session,
        symbol=symbol,
        timeframe=timeframe,
        signal_type=signal_type,
    )

    return SignalListResponse(
        items=[SignalResponse.model_validate(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
    )
