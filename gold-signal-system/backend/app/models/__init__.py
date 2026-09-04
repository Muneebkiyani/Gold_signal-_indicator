"""
Models package — exports all SQLModel table models and enums.

Import from here to guarantee every table is registered with
SQLModel.metadata before init_db() calls create_all().
"""

from app.models.enums import SignalSource, SignalType
from app.models.candle import Candle
from app.models.signal import Signal

__all__ = [
    "Candle",
    "Signal",
    "SignalType",
    "SignalSource",
]
