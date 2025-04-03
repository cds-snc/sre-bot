from datetime import datetime, timedelta, timezone
import requests
import pytz

from integrations.google_workspace import google_service
from integrations.utils.api import convert_string_to_camel_case, generate_unique_id

# Get the email for the SRE bot and the email for the delegated admin
SRE_BOT_EMAIL = google_service.SRE_BOT_EMAIL
GOOGLE_DELEGATED_ADMIN_EMAIL = google_service.GOOGLE_DELEGATED_ADMIN_EMAIL

handle_google_api_errors = google_service.handle_google_api_errors


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

    return google_service.execute_google_api_call(
        "calendar",
        "v3",
        "freebusy",
        "query",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=["https://www.googleapis.com/auth/calendar"],
        body=body,
    )


@handle_google_api_errors
def insert_event(start, end, emails, title, incident_document, **kwargs) -> dict:
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
        dict: A dictionary containing the event link and a message indicating when the event has been scheduled.
    """
    time_zone = kwargs.get("time_zone", "America/New_York")
    body = {
        "start": {"dateTime": start, "timeZone": time_zone},
        "end": {"dateTime": end, "timeZone": time_zone},
        "attendees": [{"email": email.strip()} for email in emails],
        "summary": title,
        "guestsCanModify": True,
        "guestsCanInviteOthers": True,
        "conferenceData": {
            "createRequest": {
                "requestId": generate_unique_id(),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if incident_document:
        body["attachments"] = [
            {
                "fileUrl": f"https://docs.google.com/document/d/{incident_document}",
                "mimeType": "application/vnd.google-apps.document",
                "title": "Incident Document",
            }
        ]
    else:
        # Optionally handle the case where 'incident_document' is None or empty
        # For example, remove 'attachments' from 'body' if it shouldn't exist without a valid document
        body.pop(
            "attachments", None
        )  # This removes 'attachments' if it exists, does nothing if it doesn't

    body.update({convert_string_to_camel_case(k): v for k, v in kwargs.items()})
    if "delegated_user_email" in kwargs and kwargs["delegated_user_email"] is not None:
        delegated_user_email = kwargs["delegated_user_email"]
    else:
        delegated_user_email = SRE_BOT_EMAIL

    result = google_service.execute_google_api_call(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email=delegated_user_email,
        body=body,
        calendarId="primary",
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    # Handle the instance differently if the result is a dictionary or a tuple and get the calendar link and start time
    if isinstance(result, dict):
        htmllink = result.get("htmlLink")
        start_time = result.get("start").get("dateTime")
    elif isinstance(result, tuple):
        htmllink = result[0].get("htmlLink")
        start_time = result[0].get("start").get("dateTime")

    # Convert teh date to be more human readable
    datetime_obj = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S%z")
    formatted_datetime = datetime_obj.strftime("%A, %B %d, %Y at %I:%M %p")

    # Compose a message to return indicating when the event has been scheduled
    event_info = f"Retro has been scheduled for {formatted_datetime} EDT. Check your calendar for more details."

    # Create a dictionary to return the event link and the event info
    result = dict(event_link=htmllink, event_info=event_info)

    return result


# Function to use the freebusy response to find the first available spot in the next 60 days. We look for a 30 minute windows, 3
# days in the future, ignoring weekends
def find_first_available_slot(
    freebusy_response, days_in_future, duration_minutes=30, search_days_limit=60
):
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

        search_start = search_date.replace(
            hour=starting_hour, minute=0, second=0, microsecond=0
        )  # 1 PM EST, times are in UTC
        search_end = search_date.replace(
            hour=ending_hour, minute=0, second=0, microsecond=0
        )  # 3 PM EST, times are in UTC

        # if the day is a federal holiday, skip it
        if search_date.date().strftime("%Y-%m-%d") in federal_holidays:
            continue

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


def get_federal_holidays():
    # Get the public holidays for the current year
    # Uses Paul Craig's Public holidays api to retrieve the federal holidays (https://canada-holidays.ca/api)

    # get today's year
    year = datetime.now().year

    # call the api to get the public holidays
    url = f"https://canada-holidays.ca/api/v1/holidays?federal=true&year={year}"
    response = requests.get(url, timeout=10)

    # Store the observed dates of the holidays and return the list
    holidays = []
    for holiday in response.json()["holidays"]:
        holidays.append(holiday["observedDate"])
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
    local_time = local_tz.localize(
        datetime(date.year, date.month, date.day, hour, minute)
    )

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
    start_dt = datetime.fromisoformat(time_min[:-1]).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(time_max[:-1]).replace(tzinfo=timezone.utc)

    # Check each calendar
    for email, calendar_data in freebusy_response["calendars"].items():
        # Skip if there are errors or no busy data
        if "errors" in calendar_data or "busy" not in calendar_data:
            continue

        busy_periods = calendar_data["busy"]

        if len(busy_periods) == 1:
            busy_start = datetime.fromisoformat(busy_periods[0]["start"][:-1]).replace(
                tzinfo=timezone.utc
            )
            busy_end = datetime.fromisoformat(busy_periods[0]["end"][:-1]).replace(
                tzinfo=timezone.utc
            )

            # Calculate how close the busy period is to the search period boundaries
            start_diff = abs((busy_start - start_dt).total_seconds())
            end_diff = abs((busy_end - end_dt).total_seconds())

            # If within 1 hour of both boundaries, this is likely a configuration issue
            if start_diff < 3600 and end_diff < 3600:
                unavailable_user_emails.append(email)
                continue

    return unavailable_user_emails
