"""Pure credit-window check.

The donor's credit window is the trailing N hours before each weekly reset.
Example: reset = Monday 09:00 UTC, donate_last_hours = 10
         -> window is every Sunday 23:00 UTC .. Monday 09:00 UTC.

Everything is UTC. No DST handling, no per-user timezone — donors who want
local-time semantics convert at the config layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta

WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def weekly_reset_at(now: datetime, reset_day: str, reset_hour: int) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    target_dow = WEEKDAY_NAMES[reset_day.lower()]
    candidate = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
    days_ahead = (target_dow - candidate.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate <= now:
        candidate = candidate + timedelta(days=7)
    return candidate


def is_in_credit_window(
    now: datetime,
    reset_day: str,
    reset_hour: int,
    donate_last_hours: int,
) -> bool:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if donate_last_hours <= 0:
        return False
    next_reset = weekly_reset_at(now, reset_day, reset_hour)
    window_start = next_reset - timedelta(hours=donate_last_hours)
    return window_start <= now < next_reset
