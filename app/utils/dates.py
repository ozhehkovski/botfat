from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def local_date(timezone_name: str, days_offset: int = 0) -> date:
    return (now_in_timezone(timezone_name) + timedelta(days=days_offset)).date()


def day_bounds_utc(target_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    start_local = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


def format_meal_time(dt: datetime, timezone_name: str) -> str:
    return dt.astimezone(ZoneInfo(timezone_name)).strftime("%H:%M")
