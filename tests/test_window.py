from datetime import datetime, timezone

import pytest

from agent.window import is_in_credit_window, weekly_reset_at

UTC = timezone.utc


def test_inside_window_sunday_evening():
    # reset Monday 09:00 UTC, donate last 10h => window Sun 23:00 .. Mon 09:00
    now = datetime(2026, 5, 24, 23, 30, tzinfo=UTC)  # Sunday 23:30
    assert is_in_credit_window(now, "monday", 9, 10) is True


def test_just_before_window():
    now = datetime(2026, 5, 24, 22, 59, tzinfo=UTC)  # Sun 22:59 — 1 min before
    assert is_in_credit_window(now, "monday", 9, 10) is False


def test_at_reset_boundary_is_outside():
    # the reset moment itself is the start of the *next* week, not inside the window
    now = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)  # Mon 09:00 exactly
    assert is_in_credit_window(now, "monday", 9, 10) is False


def test_mid_week_outside():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)  # Wed noon
    assert is_in_credit_window(now, "monday", 9, 10) is False


def test_full_week_window_always_true():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    assert is_in_credit_window(now, "monday", 9, 24 * 7) is True


def test_zero_hours_window_always_false():
    now = datetime(2026, 5, 24, 23, 30, tzinfo=UTC)
    assert is_in_credit_window(now, "monday", 9, 0) is False


def test_naive_datetime_raises():
    naive = datetime(2026, 5, 24, 23, 30)
    with pytest.raises(ValueError):
        is_in_credit_window(naive, "monday", 9, 10)


def test_weekly_reset_finds_next_sunday_evening():
    now = datetime(2026, 5, 24, 23, 30, tzinfo=UTC)  # Sunday
    reset = weekly_reset_at(now, "monday", 9)
    assert reset == datetime(2026, 5, 25, 9, 0, tzinfo=UTC)


def test_weekly_reset_skips_to_next_week_when_past():
    # Monday 10:00 — already past today's reset, next reset is +7 days
    now = datetime(2026, 5, 25, 10, 0, tzinfo=UTC)
    reset = weekly_reset_at(now, "monday", 9)
    assert reset == datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
