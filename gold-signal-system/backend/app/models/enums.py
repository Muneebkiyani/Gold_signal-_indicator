"""
Signal type and source enumerations.

Kept in a dedicated module so they can be imported by models,
CRUD helpers, and strategy code without circular imports.
"""

import enum


class SignalType(str, enum.Enum):
    """The four possible signal states produced by the strategy."""
    WAIT = "WAIT"           # Conditions not yet met — hold position
    BUY = "BUY"             # Long-entry signal
    SELL = "SELL"           # Short-entry signal
    NO_ENTRY = "NO_ENTRY"   # Conditions met but entry disqualified


class SignalSource(str, enum.Enum):
    """Which strategy rule generated the signal."""
    EMA_RSI_ADX = "EMA_RSI_ADX"   # EMA crossover + RSI + ADX confluence
    SMA_81 = "SMA_81"              # Price vs 81-period SMA bias filter
