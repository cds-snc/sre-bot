import pytz
from datetime import datetime
from structlog import get_logger

logger = get_logger()


def convert_utc_datetime_to_tz(
    date_time: datetime, tz: str = "America/Montreal"
) -> datetime:
    """Convert a datetime object to a specific timezone."""
    log = logger.bind(operation="convert_utc_datetime_to_tz", tz=tz)
    utc_time = date_time.replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone(tz)
    result = utc_time.astimezone(target_tz)
    log.debug("converted_datetime", result=str(result))
    return result


def convert_tz_datetime_to_utc(
    date_time: datetime, tz: str = "America/Montreal"
) -> datetime:
    """Convert a datetime object from a specific TZ to UTC timezone."""
    log = logger.bind(operation="convert_tz_datetime_to_utc", tz=tz)
    source_tz = pytz.timezone(tz)
    result = source_tz.localize(date_time).astimezone(pytz.utc)
    log.debug("converted_datetime", result=str(result))
    return result
