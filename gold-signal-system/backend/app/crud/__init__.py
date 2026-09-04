"""
CRUD package — exports helper functions for database operations.
"""

from app.crud.candle import (
    count_candles,
    create_candle,
    delete_candles,
    get_candle,
    get_candle_by_time,
    get_candles,
    get_latest_candle,
    save_candles,
)
from app.crud.signal import (
    DuplicateSignalError,
    count_signals,
    create_signal,
    get_latest_signal,
    get_pending_telegram_signals,
    get_signal,
    get_signal_by_bar,
    get_signals,
    update_telegram_status,
)

__all__ = [
    # Candle
    "create_candle",
    "get_candle",
    "get_candle_by_time",
    "get_candles",
    "get_latest_candle",
    "save_candles",
    "count_candles",
    "delete_candles",
    # Signal
    "DuplicateSignalError",
    "create_signal",
    "get_signal",
    "get_signals",
    "get_latest_signal",
    "get_signal_by_bar",
    "update_telegram_status",
    "get_pending_telegram_signals",
    "count_signals",
]
