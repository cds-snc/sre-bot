from datetime import datetime
from typing import TYPE_CHECKING, cast

from integrations.google_workspace import client as google_service_client
from integrations.utils.api import convert_string_to_camel_case, generate_unique_id

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import Event, FreeBusyRequest  # pyright: ignore[reportMissingModuleSource]

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_freebusy(time_min, time_max, items, body_kwargs=None, **kwargs):
    """Returns free/busy information for a set of calendars.

    Args:
        time_min (str): The start of the interval for the query.
        time_max (str): The end of the interval for the query.
        items (list): The list of calendars and/or groups to query.
        body_kwargs (dict, optional): Additional parameters to include in the request body. e.g. `time_zone`, `groupExpansionMax`, etc.
        **kwargs: Additional keyword arguments to pass to the API call, such as `delegated_user_email`.
    Returns:
        dict: The free/busy response for the calendars and/or groups provided.
    """

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": items,
    }
    if body_kwargs is not None and isinstance(body_kwargs, dict):
        body.update({convert_string_to_camel_case(k): v for k, v in body_kwargs.items()})

    service = google_service_client.get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    return google_service_client.execute_google_api_request(service.freebusy().query(body=cast("FreeBusyRequest", body)))


def insert_event(
    start,
    end,
    emails,
    title,
    calendar_id="primary",
    incident_document=None,
    body_kwargs=None,
    **kwargs,
) -> dict:
    """Creates a new event in the specified calendars.

    Args:
        start (datetime): The start time of the event. Must be in ISO 8601 format (e.g., '2023-04-10T10:00:00-04:00')
        end (datetime): The end time of the event.
        emails (list): The list of email addresses of the attendees.
        title (str): The title of the event.
        calendar_id (str, optional): The ID of the calendar to insert the event into. Defaults to 'primary'.
        incident_document (str, optional): The ID of the Google Document to attach to the event.
        **body_kwargs: Additional keyword arguments to pass to the event body. E.g., `time_zone`, etc. https://developers.google.com/calendar/v3/reference/events/insert
        **kwargs: Additional keyword arguments to pass to the API call. E.g., `delegated_user_email`.

    Returns:
        dict: A dictionary containing the event link and a message indicating when the event has been scheduled.
    """
    if body_kwargs is None:
        time_zone = "America/New_York"
    elif isinstance(body_kwargs, dict):
        time_zone = body_kwargs.get("time_zone", "America/New_York")
    else:
        raise ValueError(
            "body_kwargs must be a dictionary or None. If you want to pass a time zone, use body_kwargs={'time_zone': 'America/New_York'}"
        )
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
        body.pop("attachments", None)  # This removes 'attachments' if it exists, does nothing if it doesn't

    if body_kwargs is not None and isinstance(body_kwargs, dict):
        body.update({convert_string_to_camel_case(k): v for k, v in body_kwargs.items()})

    service = google_service_client.get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    result = google_service_client.execute_google_api_request(
        service.events().insert(
            calendarId=calendar_id,
            body=cast("Event", body),
            supportsAttachments=True,
            sendUpdates="all",
            conferenceDataVersion=1,
        )
    )
    htmllink = result.get("htmlLink")
    start_time = result.get("start").get("dateTime")

    # Convert teh date to be more human readable
    datetime_obj = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S%z")
    formatted_datetime = datetime_obj.strftime("%A, %B %d, %Y at %I:%M %p")

    # Compose a message to return indicating when the event has been scheduled
    event_info = f"Retro has been scheduled for {formatted_datetime} EDT. Check your calendar for more details."

    # Create a dictionary to return the event link and the event info
    result = {"event_link": htmllink, "event_info": event_info}

    return result
