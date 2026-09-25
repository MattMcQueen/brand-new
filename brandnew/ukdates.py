"""Dates and times, always in UK time (GMT/BST)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import config

UK = ZoneInfo("Europe/London")


def now_uk() -> datetime:
    return datetime.now(UK)


def today_uk() -> date:
    return now_uk().date()


def fetch_window(today: date) -> tuple[date, date]:
    """First and last release dates worth keeping when fetching."""
    return today - timedelta(days=config.PAST_FALLBACK_DAYS), today + timedelta(days=config.UPCOMING_DAYS)


def in_fetch_window(d: date, today: date) -> bool:
    start, end = fetch_window(today)
    return start <= d <= end


def format_date(d: date) -> str:
    """Fri 2 Oct 2026"""
    return f"{d:%a} {d.day} {d:%b %Y}"


def format_updated(dt: datetime) -> str:
    """Friday 25 September 2026 at 05:31 BST"""
    dt = dt.astimezone(UK)
    return f"{dt:%A} {dt.day} {dt:%B %Y at %H:%M} {dt.tzname()}"


def format_month(d: date) -> str:
    return f"{d:%B %Y}"
