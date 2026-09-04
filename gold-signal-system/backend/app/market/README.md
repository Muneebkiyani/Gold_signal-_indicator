# Phase 4 — XAUUSD Market Data Layer

This directory contains the market-data layer for the XAUUSD Gold Signal System.

## Architecture

The market-data layer uses an abstract provider interface ([`BaseMarketDataProvider`](file:///Users/mac/Documents/trading_indicator_system/gold-signal-system/backend/app/market/base_provider.py)) to ensure complete decoupling between data ingestion, strategy execution, and database persistence.

```
┌────────────────────────────────────────────────────────┐
│               BaseMarketDataProvider (ABC)              │
│  - get_latest_price(symbol)                            │
│  - get_historical_candles(symbol, timeframe, limit)    │
│  - get_latest_candle(symbol, timeframe)                │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
   TwelveDataXAUUSDProvider      MockXAUUSDProvider
   (Live Twelve Data API)        (Testing & Offline Dev)
              │                           │
              └─────────────┬─────────────┘
                            ▼
                    NormalizedCandle
        (UTC datetime, deterministic boundaries,
               standard float OHLCV)
```

---

## Provider Investigation & Selection

Before choosing a market data provider, the following free and low-cost APIs for XAUUSD (Gold Spot) were evaluated:

| Provider | XAUUSD / Gold Support | Historical OHLC | Native M15 | Rate Limit / Free Tier | Verdict |
|---|---|---|---|---|---|
| **Twelve Data** | ✅ Yes (`XAU/USD` under FOREX/Metals) | ✅ Deep intraday history | ✅ Yes (`15min`) | 8 req/min, 800 req/day | **Selected as Primary** |
| **Binance (PAXG/USDT)** | ⚠️ Gold-backed crypto token (PAX Gold) | ✅ Deep klines | ✅ Yes (`15m`) | Unlimited public API | Excellent fallback, but not raw spot XAUUSD |
| **Alpha Vantage** | ⚠️ Limited / Commodities endpoint | ⚠️ Restrictive | ❌ Requires premium for gold intraday | 25 requests/day | Too restrictive for M15 alerts |
| **Finnhub** | ⚠️ FX major pairs only on free tier | ❌ Spot gold restricted | ❌ Unavailable on free tier | 60 req/min | Spot gold requires paid plan |
| **OANDA v20** | ✅ Yes (`XAU_USD`) | ✅ Real-time + history | ✅ Yes (`M15`) | Requires brokerage account token | Not open without account signup |

### Why Twelve Data Was Selected

1. **Native XAU/USD Support**: Direct spot gold quotes under standard commodities/metals ticker `XAU/USD`.
2. **Direct 15-Minute Candles**: Native `interval=15min` support without needing client-side bar synthesis or tick aggregation.
3. **Generous Free Tier**: 800 requests per day and 8 requests per minute. Since this is an M15 alert system polling either once every 15 minutes or once per minute on candle close, 800 credits/day is more than sufficient.
4. **Reliable REST API & Documentation**: Fully documented JSON REST API with clear error payloads (`{"status": "error", "code": 401, "message": "..."}`).
5. **Deterministic UTC Timestamps**: Timestamps are provided in ISO/standard UTC format and converted cleanly to timezone-aware UTC.

---

## Normalized Candle Format

All providers return the application-wide normalized candle:

```python
class NormalizedCandle(BaseModel):
    timestamp: datetime   # Timezone-aware UTC open time (aligned to M15 boundary)
    open: float           # Bar open price
    high: float           # Bar high price
    low: float            # Bar low price
    close: float          # Bar close price
    volume: float         # Volume (or lot volume)
```

### Deterministic Boundaries

Timestamps are aligned to the candle open boundary using `align_to_boundary(dt, timeframe)`:
- For `M15`: Minutes are bucketed into `00`, `15`, `30`, `45` with seconds and microseconds set to `0`.
- All timestamps carry explicit `timezone.utc`.

---

## Configuration

Set the API key in `.env`:

```bash
DATA_PROVIDER_API_KEY=your_twelve_data_api_key
DATA_PROVIDER_BASE_URL=https://api.twelvedata.com
```

If no API key is provided, the factory `get_market_provider("mock")` can be used for offline development and testing.
