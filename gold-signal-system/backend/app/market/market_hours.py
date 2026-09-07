"""
Market Hours Validation for XAUUSD (Spot Gold).

Standard Global Spot Gold (CME / Interbank) Market Schedule (UTC):
- Opens: Sunday 22:00 UTC (5:00 PM EST / 3:00 AM Monday PKT)
- Closes: Friday 21:00 UTC (5:00 PM EST / 2:00 AM Saturday PKT)
- Daily Rollover Break (Mon-Thu): 21:00 to 22:00 UTC (maintenance window)
- Weekend: Friday 21:00 UTC through Sunday 22:00 UTC (Closed)
"""

from datetime import datetime, timezone
from typing import Optional, Tuple


def is_gold_market_open(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Check if the XAUUSD (Gold Spot) interbank market is officially open.
    Returns (is_open: bool, status_reason: str).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # 0 = Monday, ..., 4 = Friday, 5 = Saturday, 6 = Sunday
    weekday = dt.weekday()
    hour = dt.hour

    # 1. Saturday: Closed all day
    if weekday == 5:
        return False, "Market Closed (Weekend: Saturday)"

    # 2. Sunday: Closed until 22:00 UTC (5:00 PM EST)
    if weekday == 6:
        if hour < 22:
            return False, "Market Closed (Weekend: Sunday - Opens at 22:00 UTC / 5:00 PM EST)"
        return True, "Market Open (Asian / Pacific Session)"

    # 3. Friday: Closes at 21:00 UTC (5:00 PM EST)
    if weekday == 4:
        if hour >= 21:
            return False, "Market Closed (Weekend: Friday Close)"
        return True, "Market Open (US / London Session)"

    # 4. Monday through Thursday:
    # Daily settlement / rollover break from 21:00 to 22:00 UTC
    if hour == 21:
        return False, "Market Closed (Daily Rollover / Maintenance Break 21:00-22:00 UTC)"

    return True, "Market Open"


def is_live_candle(candle_time: datetime, max_age_minutes: int = 30) -> bool:
    """
    Verify if a candle closed recently (live real-time market bar) vs.
    an older historical candle from startup backfill.
    """
    now = datetime.now(timezone.utc)
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=timezone.utc)
    else:
        candle_time = candle_time.astimezone(timezone.utc)

    age_seconds = (now - candle_time).total_seconds()
    # Allow candles up to max_age_minutes old (plus a slight margin for clock drift)
    return -60 <= age_seconds <= (max_age_minutes * 60)
