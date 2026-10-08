"""Time helpers. Everything is stored in UTC; wall-clock maths goes through zoneinfo."""

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

QUANTUM_MINUTES = 15
QUANTUM = dt.timedelta(minutes=QUANTUM_MINUTES)
DEFAULT_TIMEZONE = "Asia/Manila"


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def is_valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def to_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return value.astimezone(dt.UTC)


def is_quantum_aligned(value: dt.datetime) -> bool:
    return value.second == 0 and value.microsecond == 0 and value.minute % QUANTUM_MINUTES == 0


def quanta(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """Every 15-minute slot start in [start, end)."""
    slots = []
    cursor = start
    while cursor < end:
        slots.append(cursor)
        cursor += QUANTUM
    return slots


def local_midnight_utc(day: dt.date, tz: ZoneInfo) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(0, 0), tzinfo=tz).astimezone(dt.UTC)


def at_local_minute(day: dt.date, minute: int, tz: ZoneInfo) -> dt.datetime:
    """UTC instant for `minute` minutes after local midnight on `day` (1440 = next midnight)."""
    local = dt.datetime.combine(day, dt.time(0, 0), tzinfo=tz) + dt.timedelta(minutes=minute)
    # Re-attach the zone so a DST shift between midnight and `minute` is honoured.
    local = dt.datetime.combine(local.date(), local.time(), tzinfo=tz)
    return local.astimezone(dt.UTC)


def local_date_and_minute(value: dt.datetime, tz: ZoneInfo) -> tuple[dt.date, int]:
    local = value.astimezone(tz)
    return local.date(), local.hour * 60 + local.minute


def minute_label(minute: int) -> str:
    hour, rest = divmod(minute % 1440, 60)
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{rest:02d} {suffix}"
