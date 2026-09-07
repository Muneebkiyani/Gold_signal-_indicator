from datetime import datetime, timezone
from app.market.market_hours import is_gold_market_open, is_live_candle


def test_market_closed_on_saturday():
    # Saturday, Sep 5 2026, 12:00 UTC
    sat = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    is_open, reason = is_gold_market_open(sat)
    assert not is_open
    assert "Saturday" in reason


def test_market_closed_on_sunday_before_open():
    # Sunday, Sep 6 2026, 15:00 UTC (before 22:00 UTC)
    sun_early = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)
    is_open, reason = is_gold_market_open(sun_early)
    assert not is_open
    assert "Sunday" in reason


def test_market_opens_sunday_evening():
    # Sunday, Sep 6 2026, 22:15 UTC (after 22:00 UTC)
    sun_open = datetime(2026, 9, 6, 22, 15, tzinfo=timezone.utc)
    is_open, reason = is_gold_market_open(sun_open)
    assert is_open
    assert "Market Open" in reason


def test_market_open_during_week():
    # Wednesday, Sep 2 2026, 14:00 UTC (US/London session)
    wed = datetime(2026, 9, 2, 14, 0, tzinfo=timezone.utc)
    is_open, reason = is_gold_market_open(wed)
    assert is_open
    assert reason == "Market Open"


def test_market_closed_on_friday_evening():
    # Friday, Sep 4 2026, 21:30 UTC (after 21:00 UTC close)
    fri_late = datetime(2026, 9, 4, 21, 30, tzinfo=timezone.utc)
    is_open, reason = is_gold_market_open(fri_late)
    assert not is_open
    assert "Friday Close" in reason


def test_is_live_candle():
    now = datetime.now(timezone.utc)
    # Candle 5 minutes ago -> live
    recent = datetime.fromtimestamp(now.timestamp() - 300, tz=timezone.utc)
    assert is_live_candle(recent, max_age_minutes=30) is True

    # Candle 3 hours ago -> historical
    old = datetime.fromtimestamp(now.timestamp() - (3 * 3600), tz=timezone.utc)
    assert is_live_candle(old, max_age_minutes=30) is False
