"""Local time of the school <-> UTC in the database. The timezone comes from the ENV `SCHOOL_TZ`
(default Europe/Berlin; the language course runs in WIB = Asia/Jakarta, set in msh_config.json).

Sessions are entered and displayed in local time ("25.09.2026, 10:00 Uhr"),
what is stored is `timestamptz` in UTC. The browser does NOT convert on its own —
the API delivers date and time in local time along with it, so that a device in
a different timezone shows the same times as the school.
"""
import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ_NAME = os.environ.get('SCHOOL_TZ') or 'Europe/Berlin'    # also used in SQL (`timezone(TZ_NAME, column)`)
TZ = ZoneInfo(TZ_NAME)


def to_utc(day, hhmm):
    """date + 'HH:MM' (local time) -> aware datetime in UTC."""
    local = datetime.combine(day, time.fromisoformat(hhmm), tzinfo=TZ)
    return local.astimezone(timezone.utc)


def local_parts(moment):
    """aware datetime -> ('YYYY-MM-DD', 'HH:MM') in local time."""
    local = moment.astimezone(TZ)
    return local.date().isoformat(), local.strftime('%H:%M')


def day_start_utc(day):
    """Start of a local-time day in UTC (for period queries)."""
    return datetime.combine(day, time(0, 0), tzinfo=TZ).astimezone(timezone.utc)


def day_range_utc(first, last):
    """[start of `first`, start of the day after `last`) in UTC."""
    return day_start_utc(first), day_start_utc(last + timedelta(days=1))


def tz_label():
    """Short name of the school's timezone for hint texts (WIB; Europe/Berlin CEST/CET depending on the date)."""
    return datetime.now(TZ).tzname()


def today():
    return datetime.now(TZ).date()


def de_day(day):
    """date or 'YYYY-MM-DD' -> '25.09.2026' — THE ONE German date formatting in the server
    (activity log, hints, CSV). Empty -> '–', anything else stays unchanged."""
    if not day:
        return '–'
    if isinstance(day, str):
        try:
            day = date.fromisoformat(day)
        except ValueError:
            return day
    return day.strftime('%d.%m.%Y')
