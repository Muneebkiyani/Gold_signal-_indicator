# Phase 6 — Technical Indicator Engine

This directory implements technical indicator calculations reproducing TradingView / Pine Script v5 behavior.

---

## Supported Indicators & Configurations

| Indicator | Parameter | Formula / Pine Function | Purpose |
|---|---|---|---|
| **Fast EMA** | `EMA_FAST = 9` | `ta.ema(close, 9)` | Fast momentum trend tracking |
| **Slow EMA** | `EMA_SLOW = 21` | `ta.ema(close, 21)` | Slow baseline trend tracking |
| **RSI** | `RSI_LENGTH = 14` | `ta.rsi(close, 14)` | Momentum oscillator (overbought/oversold) |
| **+DI / -DI** | `ADX_LENGTH = 14` | `ta.dmi(14, 14)[0, 1]` | Directional movement indicators |
| **ADX** | `ADX_SMOOTHING = 14` | `ta.dmi(14, 14)[2]` | Trend strength filter (min 20) |
| **SMA 81** | `SMA_LENGTH = 81` | `ta.sma(close, 81)` | Macro trend baseline filter |
| **ATR** | `ATR_LENGTH = 14` | `ta.atr(14)` | Volatility measurement |

---

## TradingView / Pine Script Equivalences & Nuances

### 1. Wilder Smoothing (RMA)
In TradingView, `ta.rma(source, length)` is defined as:
$$\alpha = \frac{1}{\text{length}}$$
$$\text{RMA}_t = \alpha \cdot x_t + (1 - \alpha) \cdot \text{RMA}_{t-1} = \frac{x_t + (\text{length} - 1) \cdot \text{RMA}_{t-1}}{\text{length}}$$
- **Initialization**: The first valid value at index `length - 1` is initialized as the **Simple Moving Average (SMA)** of the first `length` items.
- Used internally by **RSI**, **ATR**, and **DMI (+DI, -DI, ADX)**.

### 2. Exponential Moving Average (EMA)
In TradingView, `ta.ema(source, length)` uses:
$$\alpha = \frac{2}{\text{length} + 1}$$
$$\text{EMA}_t = \alpha \cdot x_t + (1 - \alpha) \cdot \text{EMA}_{t-1}$$
- **Initialization**: Initialized with the SMA of the first `length` elements at index `length - 1`.

### 3. Relative Strength Index (RSI)
TradingView calculates RSI as:
$$\text{change}_t = \text{close}_t - \text{close}_{t-1}$$
$$\text{up} = \text{ta.rma}(\max(\text{change}, 0), 14)$$
$$\text{down} = \text{ta.rma}(\max(-\text{change}, 0), 14)$$
$$\text{RSI} = 100 - \frac{100}{1 + \frac{\text{up}}{\text{down}}}$$

### 4. Average Directional Index (ADX) & DMI
TradingView calculates `ta.dmi(diLength, adxSmoothing)` as:
1. $\text{up} = \text{high}_t - \text{high}_{t-1}$, $\text{down} = \text{low}_{t-1} - \text{low}_t$
2. $\text{+DM} = \text{up} > \text{down} \text{ and } \text{up} > 0 \ ?\ \text{up} : 0$
3. $\text{-DM} = \text{down} > \text{up} \text{ and } \text{down} > 0 \ ?\ \text{down} : 0$
4. $\text{TR} = \max(\text{high}_t - \text{low}_t, |\text{high}_t - \text{close}_{t-1}|, |\text{low}_t - \text{close}_{t-1}|)$
5. $\text{+DI} = 100 \cdot \frac{\text{rma}(\text{+DM}, 14)}{\text{rma}(\text{TR}, 14)}$
6. $\text{-DI} = 100 \cdot \frac{\text{rma}(\text{-DM}, 14)}{\text{rma}(\text{TR}, 14)}$
7. $\text{DX} = 100 \cdot \frac{|\text{+DI} - \text{-DI}|}{\text{+DI} + \text{-DI}}$
8. $\text{ADX} = \text{rma}(\text{DX}, 14)$

### 5. Average True Range (ATR)
TradingView's `ta.atr(14)` is:
$$\text{ATR} = \text{ta.rma}(\text{ta.tr}, 14)$$

---

## Output Structure

The calculation produces an immutable [`IndicatorValues`](file:///Users/mac/Documents/trading_indicator_system/gold-signal-system/backend/app/strategy/engine.py) snapshot:

```python
class IndicatorValues(BaseModel):
    ema_fast: Optional[float]  # Fast EMA (9)
    ema_slow: Optional[float]  # Slow EMA (21)
    rsi: Optional[float]       # RSI (14)
    adx: Optional[float]       # ADX (14)
    di_plus: Optional[float]   # +DI (14)
    di_minus: Optional[float]  # -DI (14)
    sma_81: Optional[float]    # SMA (81)
    atr: Optional[float]       # ATR (14)
```
