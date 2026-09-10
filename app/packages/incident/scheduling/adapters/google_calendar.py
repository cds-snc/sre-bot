import random
import string
from datetime import datetime
from typing import TYPE_CHECKING, cast

import structlog
from googleapiclient.errors import HttpError

from integrations.google_workspace.client import classify_google_error, get_calendar_service

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import Event, FreeBusyRequest  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def generate_unique_id() -> str:
    # Define the characters to use in the ID
    chars = string.ascii_lowercase + string.digits

    # Function to generate a segment of three characters
    def generate_segment():
        return "".join(random.choices(chars, k=3))  # noqa: S311 -- non-secret readable ID, not used for security tokens

    # Generate the three segments and join them with hyphens
    segments = [generate_segment() for _ in range(3)]
    unique_id = "-".join(segments)

    return unique_id


def get_freebusy(time_min, time_max, items, **kwargs):
    """Return the free/busy response for the requested calendars."""
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": items,
    }

    service = get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    try:
        return service.freebusy().query(body=cast("FreeBusyRequest", body)).execute()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise


def insert_event(
    start,
    end,
    emails,
    title,
    calendar_id="primary",
    incident_document=None,
    **kwargs,
) -> dict:
    """Create a new calendar event and return the scheduled metadata."""
    time_zone = "America/New_York"

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
        body.pop("attachments", None)

    service = get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    try:
        result = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=cast("Event", body),
                supportsAttachments=True,
                sendUpdates="all",
                conferenceDataVersion=1,
            )
            .execute()
        )
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise

    htmllink = result.get("htmlLink")
    start_time = result.get("start").get("dateTime")
    datetime_obj = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S%z")
    formatted_datetime = datetime_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    event_info = f"Retro has been scheduled for {formatted_datetime} EDT. Check your calendar for more details."
    return {"event_link": htmllink, "event_info": event_info}
