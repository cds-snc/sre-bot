"""Pure availability computations over an already-fetched freebusy response."""

from datetime import UTC, datetime, timedelta

import pytz
import requests
import structlog

logger = structlog.get_logger()


# Function to use the freebusy response to find the first available spot in the next 60 days. We look for a 30 minute windows, 3
# days in the future, ignoring weekends
def find_first_available_slot(freebusy_response, days_in_future, duration_minutes=30, search_days_limit=60):
    # EST timezone
    est = pytz.timezone("US/Eastern")

    starting_hour = get_utc_hour(13, 0, "US/Eastern")
    ending_hour = get_utc_hour(15, 0, "US/Eastern")

    # Combine all busy times into a single list and sort them
    busy_times = []
    for calendar in freebusy_response["calendars"].values():
        for busy_period in calendar["busy"]:
            # convert from iso 8601 standard to datetime
            start = datetime.fromisoformat(busy_period["start"][:-1])
            end = datetime.fromisoformat(busy_period["end"][:-1])
            busy_times.append((start, end))
    busy_times.sort(key=lambda x: x[0])

    # get the list of Canandian federal holidays
    federal_holidays = get_federal_holidays()

    for day_offset in range(days_in_future, days_in_future + search_days_limit):
        # Calculate the start and end times of the search window for the current day
        search_date = datetime.utcnow() + timedelta(days=day_offset)

        # Check if the day is Saturday (5) or Sunday (6) and skip it
        if search_date.weekday() in [5, 6]:
            continue

        search_start = search_date.replace(hour=starting_hour, minute=0, second=0, microsecond=0)  # 1 PM EST, times are in UTC
        search_end = search_date.replace(hour=ending_hour, minute=0, second=0, microsecond=0)  # 3 PM EST, times are in UTC

        # if the day is a federal holiday, skip it
        if search_date.date().strftime("%Y-%m-%d") in federal_holidays:
            continue

        # Attempt to find an available slot within this day's search window
        for current_time in (search_start + timedelta(minutes=i) for i in range(0, 121, duration_minutes)):
            slot_end = current_time + timedelta(minutes=duration_minutes)
            if all(slot_end <= start or current_time >= end for start, end in busy_times) and slot_end <= search_end:
                # return the time and convert them to EST timezone
                return current_time.astimezone(est), slot_end.astimezone(est)

    return None, None  # No available slot found after searching the limit


def get_federal_holidays():
    # Get the public holidays for the current year
    # Uses Paul Craig's Public holidays api to retrieve the federal holidays (https://canada-holidays.ca/api)
    holidays = []

    # get today's year
    year = datetime.now().year

    # call the api to get the public holidays
    url = f"https://canada-holidays.ca/api/v1/holidays?federal=true&year={year}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        for holiday in response.json().get("holidays", []):
            holidays.append(holiday["observedDate"])
    except requests.exceptions.RequestException as e:
        logger.error(
            "federal_holidays_request_failed",
            error=str(e),
            year=year,
        )
    return holidays


def get_utc_hour(hour, minute, tz_name, date=None):
    """
    Converts a specific time in a given time zone to UTC and returns the hour.

    Args:
        hour (int): The hour of the time in 24-hour format.
        minute (int): The minute of the time.
        tz_name (str): The name of the time zone (e.g., "US/Eastern").

    Returns:
        str: The corresponding UTC hour.
    """
    # Define the local timezone
    local_tz = pytz.timezone(tz_name)

    # If we are not passing the date, then initialize it to the current date:w
    if date is None:
        date = datetime.utcnow()

    # Create a datetime object for the given time in the local timezone
    local_time = local_tz.localize(datetime(date.year, date.month, date.day, hour, minute))

    # Convert to UTC
    utc_time = local_time.astimezone(pytz.utc)

    return utc_time.hour


def identify_unavailable_users(freebusy_response, time_min: str, time_max: str):
    """
    Identifies users who appear to have calendar configuration issues
    or are completely unavailable during the entire specified time range.

    Args:
        freebusy_response (dict): Response from the freebusy API
        time_min (str): ISO format string for start time with 'Z' suffix
        time_max (str): ISO format string for end time with 'Z' suffix

    Returns:
        list: List of emails of users with potential calendar issues
    """
    unavailable_user_emails = []

    # Convert time_min and time_max to datetime objects
    start_dt = datetime.fromisoformat(time_min[:-1]).replace(tzinfo=UTC)
    end_dt = datetime.fromisoformat(time_max[:-1]).replace(tzinfo=UTC)

    # Check each calendar
    for email, calendar_data in freebusy_response["calendars"].items():
        # Skip if there are errors or no busy data
        if "errors" in calendar_data or "busy" not in calendar_data:
            continue

        busy_periods = calendar_data["busy"]

        if len(busy_periods) == 1:
            busy_start = datetime.fromisoformat(busy_periods[0]["start"][:-1]).replace(tzinfo=UTC)
            busy_end = datetime.fromisoformat(busy_periods[0]["end"][:-1]).replace(tzinfo=UTC)

            # Calculate how close the busy period is to the search period boundaries
            start_diff = abs((busy_start - start_dt).total_seconds())
            end_diff = abs((busy_end - end_dt).total_seconds())

            # If within 1 hour of both boundaries, this is likely a configuration issue
            if start_diff < 3600 and end_diff < 3600:
                unavailable_user_emails.append(email)
                continue

    return unavailable_user_emails
