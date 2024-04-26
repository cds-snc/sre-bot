import os
from datetime import datetime, timedelta

import pytz

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
    DEFAULT_DELEGATED_ADMIN_EMAIL,
)
from integrations.utils.api import convert_string_to_camel_case

# Get the email for the SRE bot
SRE_BOT_EMAIL = os.environ.get("SRE_BOT_EMAIL")


@handle_google_api_errors
def get_freebusy(time_min, time_max, items, **kwargs):
    """Returns free/busy information for a set of calendars.

    Args:
        time_min (str): The start of the interval for the query.
        time_max (str): The end of the interval for the query.
        items (list): The list of calendars and/or groups to query.
        time_zone (str, optional): The time zone for the query. Default is 'UTC'.
        calendar_expansion_max (int, optional): The maximum number of calendar identifiers to be provided for a single group. Maximum value is 50.
        group_expansion_max (int, optional): The maximum number of group members to return for a single group. Maximum value is 100.

    Returns:
        dict: The free/busy response for the calendars and/or groups provided.
    """

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": items,
    }
    body.update({convert_string_to_camel_case(k): v for k, v in kwargs.items()})
    
    return execute_google_api_call(
        "calendar",
        "v3",
        "freebusy",
        "query",
        delegated_user_email=DEFAULT_DELEGATED_ADMIN_EMAIL,
        scopes=["https://www.googleapis.com/auth/calendar"],
        body=body,
    )


@handle_google_api_errors
def insert_event(start, end, emails, title, **kwargs):
    """Creates a new event in the specified calendars.

    Args:
        start (datetime): The start time of the event. Must be in ISO 8601 format (e.g., '2023-04-10T10:00:00-04:00')
        end (datetime): The end time of the event.
        emails (list): The list of email addresses of the attendees.
        title (str): The title of the event.
        delegated_user_email (str, optional): The email address of the user to impersonate.
        Any additional kwargs will be added to the event body. For a full list of possible kwargs, refer to the Google Calendar API documentation:
        https://developers.google.com/calendar/v3/reference/events/insert

    Returns:
        str: The link to the created event.
    """
    time_zone = kwargs.get("time_zone", "America/New_York")
    body = {
        "start": {"dateTime": start, "timeZone": time_zone},
        "end": {"dateTime": end, "timeZone": time_zone},
        "attendees": [{"email": email.strip()} for email in emails],
        "summary": title,
        "guestsCanModify": True,
    }
    body.update({convert_string_to_camel_case(k): v for k, v in kwargs.items()})
    if "delegated_user_email" in kwargs and kwargs["delegated_user_email"] is not None:
        delegated_user_email = kwargs["delegated_user_email"]
    else:
        delegated_user_email = os.environ.get("SRE_BOT_EMAIL")

    result = execute_google_api_call(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email=delegated_user_email,
        body=body,
        calendarId="primary",
    )
    return result.get("htmlLink")


# Function to use the freebusy response to find the first available spot in the next 60 days. We look for a 30 minute windows, 3
# days in the future, ignoring weekends
def find_first_available_slot(
    freebusy_response, days_in_future, duration_minutes=30, search_days_limit=60
):
    # EST timezone
    est = pytz.timezone("US/Eastern")

    # Combine all busy times into a single list and sort them
    busy_times = []
    for calendar in freebusy_response["calendars"].values():
        for busy_period in calendar["busy"]:
            # convert from iso 8601 standard to datetime
            start = datetime.fromisoformat(busy_period["start"][:-1])
            end = datetime.fromisoformat(busy_period["end"][:-1])
            busy_times.append((start, end))
    busy_times.sort(key=lambda x: x[0])

    for day_offset in range(days_in_future, days_in_future + search_days_limit):
        # Calculate the start and end times of the search window for the current day
        search_date = datetime.utcnow() + timedelta(days=day_offset)

        # Check if the day is Saturday (5) or Sunday (6) and skip it
        if search_date.weekday() in [5, 6]:
            continue

        search_start = search_date.replace(
            hour=17, minute=0, second=0, microsecond=0
        )  # 1 PM EST, times are in UTC
        search_end = search_date.replace(
            hour=19, minute=0, second=0, microsecond=0
        )  # 3 PM EST, times are in UTC

        # Attempt to find an available slot within this day's search window
        for current_time in (
            search_start + timedelta(minutes=i) for i in range(0, 121, duration_minutes)
        ):
            slot_end = current_time + timedelta(minutes=duration_minutes)
            if all(
                slot_end <= start or current_time >= end for start, end in busy_times
            ):
                if slot_end <= search_end:
                    # return the time and convert them to EST timezone
                    return current_time.astimezone(est), slot_end.astimezone(est)

    return None, None  # No available slot found after searching the limit
