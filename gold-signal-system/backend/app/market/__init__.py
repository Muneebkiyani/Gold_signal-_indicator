"""
Market data package — replaceable provider architecture for XAUUSD market data.
"""

from app.market.base_provider import BaseMarketDataProvider
from app.market.candle_manager import (
    M15CandleManager,
    db_to_normalized,
    normalized_to_db,
)
from app.market.models import (
    MalformedDataError,
    MarketDataError,
    NormalizedCandle,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
    align_to_boundary,
    align_to_m15_boundary,
)
from app.market.xauusd_provider import (
    MockXAUUSDProvider,
    TwelveDataXAUUSDProvider,
    format_symbol_for_twelvedata,
    get_market_provider,
)

__all__ = [
    # Base interface
    "BaseMarketDataProvider",
    # Candle Manager
    "M15CandleManager",
    "db_to_normalized",
    "normalized_to_db",
    # Data models & boundary utilities
    "NormalizedCandle",
    "align_to_boundary",
    "align_to_m15_boundary",
    # Providers & factory
    "TwelveDataXAUUSDProvider",
    "MockXAUUSDProvider",
    "get_market_provider",
    "format_symbol_for_twelvedata",
    # Exceptions
    "MarketDataError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ProviderResponseError",
    "MalformedDataError",
]
