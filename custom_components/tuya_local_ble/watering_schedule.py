"""Hoselink schedule codec, based on locally captured device reports.

Unknown bytes and reserved flag bits are retained when editing. Commands and
reports have different framing; commands must never be treated as device state.
"""

from __future__ import annotations

from datetime import date, time
from struct import pack, unpack

NORMAL_DP = 101
CYCLIC_DP = 102
WEEKDAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
RECURRENCES = {"weekly": 0x00, "odd_days": 0x10, "even_days": 0x20, "interval": 0x40}


def parse_report(dp_id: int, value: bytes) -> list[bytes]:
    """Validate report framing without discarding unknown record fields."""
    size = 14 if dp_id == NORMAL_DP else 12
    if not isinstance(value, bytes) or not value or value[0] != 0:
        raise ValueError("Invalid schedule report prefix")
    if len(value) > 128 or (len(value) - 1) % size:
        raise ValueError("Invalid schedule report length")
    records = [value[pos : pos + size] for pos in range(1, len(value), size)]
    if len({record[0] for record in records}) != len(records):
        raise ValueError("Duplicate schedule IDs in report")
    return records


def minutes(value: str) -> int:
    """Accept a minute-resolution local time, including HA time selectors."""
    parsed = time.fromisoformat(value)
    if parsed.second or parsed.microsecond or parsed.tzinfo:
        raise ValueError("Schedule times must use whole minutes without a timezone")
    return parsed.hour * 60 + parsed.minute


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def weekday_mask(days: list[str]) -> int:
    if not days or any(day not in WEEKDAYS for day in days):
        raise ValueError("Select at least one valid weekday")
    return sum(1 << WEEKDAYS.index(day) for day in set(days))


def bounded(value: int, maximum: int, name: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def normal_record(
    *,
    outlet: int,
    start_time: str,
    duration: int,
    enabled: bool = True,
    recurrence: str = "weekly",
    weekdays: list[str] | None = None,
    start_date: str | None = None,
    interval_days: int = 1,
    existing: bytes | None = None,
) -> bytes:
    """Build a complete record; ID is a placeholder for creates."""
    bounded(outlet, 2, "Outlet")
    bounded(duration, 1440, "Duration in minutes")
    if recurrence not in RECURRENCES:
        raise ValueError("Unsupported recurrence")
    if recurrence == "interval" and not start_date:
        raise ValueError("Every-X-days schedules require a start date")
    if recurrence != "weekly" and weekdays:
        raise ValueError("Weekdays apply only to weekly schedules")
    if recurrence != "interval" and interval_days != 1:
        raise ValueError("Interval days apply only to every-X-days schedules")
    mask = weekday_mask(weekdays or []) if recurrence == "weekly" else 0
    day = (
        date.fromisoformat(start_date)
        if start_date
        else (date(*unpack(">HBB", existing[8:12])) if existing else date.today())
    )
    interval = bounded(interval_days, 255, "Interval days")
    reserved = existing[7] & 0x0E if existing else 0
    flags = reserved | RECURRENCES[recurrence] | int(enabled)
    return bytes([existing[0] if existing else 0]) + pack(
        ">HHBBBHBBBB",
        minutes(start_time),
        duration,
        mask,
        existing[6] if existing else 100,
        flags,
        day.year,
        day.month,
        day.day,
        interval,
        outlet - 1,
    )


def cyclic_record(
    *,
    outlet: int,
    start_time: str,
    end_time: str,
    duration: int,
    interval: int,
    weekdays: list[str],
    enabled: bool = True,
    existing: bytes | None = None,
) -> bytes:
    bounded(outlet, 2, "Outlet")
    bounded(duration, 1440, "Duration in minutes")
    bounded(interval, 1440, "Interval in minutes")
    start, end = minutes(start_time), minutes(end_time)
    if end <= start:
        raise ValueError(
            "End time must follow start time; overnight cycles are unverified"
        )
    flags = (existing[1] & 0xFC if existing else 0) | ((outlet - 1) << 1) | int(enabled)
    return pack(
        ">BBBHHHHB",
        existing[0] if existing else 0,
        flags,
        weekday_mask(weekdays),
        start,
        end,
        duration,
        interval,
        existing[11] if existing else 100,
    )


def set_enabled(dp_id: int, record: bytes, enabled: bool) -> bytes:
    result = bytearray(record)
    offset = 7 if dp_id == NORMAL_DP else 1
    result[offset] = (result[offset] & ~1) | int(enabled)
    return bytes(result)


def describe(dp_id: int, record: bytes) -> dict:
    """Expose readable device state, including unknown recurrence values."""
    if dp_id == NORMAL_DP:
        start, duration = unpack(">HH", record[1:5])
        mode = record[7] & 0xF0
        return {
            "id": record[0],
            "outlet": record[13] + 1,
            "enabled": bool(record[7] & 1),
            "start_time": clock(start),
            "duration": duration,
            "weekdays": [
                day for bit, day in enumerate(WEEKDAYS) if record[5] & (1 << bit)
            ],
            "recurrence": next(
                (key for key, value in RECURRENCES.items() if value == mode),
                f"unknown_{mode}",
            ),
            "start_date": f"{int.from_bytes(record[8:10], 'big'):04d}-{record[10]:02d}-{record[11]:02d}",
            "interval_days": record[12],
        }
    start, end, duration, interval = unpack(">HHHH", record[3:11])
    return {
        "id": record[0],
        "outlet": ((record[1] >> 1) & 1) + 1,
        "enabled": bool(record[1] & 1),
        "start_time": clock(start),
        "end_time": clock(end),
        "duration": duration,
        "interval": interval,
        "weekdays": [day for bit, day in enumerate(WEEKDAYS) if record[2] & (1 << bit)],
    }
