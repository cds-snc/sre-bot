import pytz
from datetime import datetime


def convert_utc_datetime_to_tz(
    date_time: datetime, tz: str = "America/Montreal"
) -> datetime:
    """Convert a datetime object to a specific timezone."""
    utc_time = date_time.replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone(tz)
    return utc_time.astimezone(target_tz)


def convert_tz_datetime_to_utc(
    date_time: datetime, tz: str = "America/Montreal"
) -> datetime:
    """Convert a datetime object from a specific TZ to UTC timezone."""
    source_tz = pytz.timezone(tz)
    return source_tz.localize(date_time).astimezone(pytz.utc)
