"""Unit tests for google_calendar module."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import google_calendar

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def calendar_client(monkeypatch):
    """Patch the Calendar service factory and expose the mocked stub-typed Resource chain."""
    if not hasattr(google_client, "get_calendar_service"):
        pytest.fail("integrations.google_workspace.client.get_calendar_service is not implemented")

    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_calendar_service", factory)
    if hasattr(google_calendar, "get_calendar_service"):
        monkeypatch.setattr(google_calendar, "get_calendar_service", factory)
    return SimpleNamespace(factory=factory, service=service)


# Fixture to mock the event details JSON string
@pytest.fixture
def event_details():
    return json.dumps(
        {
            "emails": ["user1@example.com", "user2@example.com"],
            "topic": "Incident Response Meeting",
        }
    )


# Fixture to mock the calendar service object
@pytest.fixture
def calendar_service_mock():
    # Mock for the Google Calendar service object
    service_mock = MagicMock()

    # Properly set the return value for the execute method to return the expected dictionary directly
    service_mock.events.return_value.insert.return_value.execute.return_value = {
        "htmlLink": "https://calendar.google.com/event_link"
    }

    return service_mock


@pytest.fixture
def items():
    return [{"id": "calendar1"}, {"id": "calendar2"}]


def test_get_freebusy_required_args_only(calendar_client, items):
    query = calendar_client.service.freebusy.return_value.query
    query.return_value.execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"

    google_calendar.get_freebusy(time_min, time_max, items)

    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email=None)
    query.assert_called_once_with(
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
        },
    )
    query.return_value.execute.assert_called_once_with()


def test_get_freebusy_passes_delegated_user_email(calendar_client, items):
    query = calendar_client.service.freebusy.return_value.query
    query.return_value.execute.return_value = {}

    google_calendar.get_freebusy(
        "2022-01-01T00:00:00Z",
        "2022-01-02T00:00:00Z",
        items,
        delegated_user_email="custom@example.com",
    )

    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email="custom@example.com")


def test_get_freebusy_optional_args(calendar_client, items):
    query = calendar_client.service.freebusy.return_value.query
    query.return_value.execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    time_zone = "America/Los_Angeles"
    calendar_expansion_max = 20
    group_expansion_max = 30
    body_kwargs = {
        "timeZone": time_zone,
        "calendarExpansionMax": calendar_expansion_max,
        "groupExpansionMax": group_expansion_max,
    }

    google_calendar.get_freebusy(time_min, time_max, items, body_kwargs=body_kwargs)

    query.assert_called_once_with(
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
            "timeZone": "America/Los_Angeles",
            "calendarExpansionMax": 20,
            "groupExpansionMax": 30,
        },
    )


def test_get_freebusy_returns_object(calendar_client):
    calendar_client.service.freebusy.return_value.query.return_value.execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    items = ["calendar1", "calendar2"]

    result = google_calendar.get_freebusy(time_min, time_max, items)

    assert isinstance(result, dict)


def test_get_freebusy_propagates_http_error(calendar_client, items):
    error = _http_error(429)
    calendar_client.service.freebusy.return_value.query.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_calendar.get_freebusy("2022-01-01T00:00:00Z", "2022-01-02T00:00:00Z", items)

    assert exc_info.value is error


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_no_kwargs_no_delegated_email(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    calendar_client,
):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {
            "dateTime": "2024-07-25T13:30:00-04:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2024-07-25T14:00:00-04:00",
            "timeZone": "America/New_York",
        },
    }
    mock_unique_id.return_value = "abc-123-de4"
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = "test_document_id"
    result = google_calendar.insert_event(start, end, emails, title, incident_document=document_id)
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email=None)
    insert.assert_called_once_with(
        calendarId="primary",
        body={
            "start": {"dateTime": start, "timeZone": "America/New_York"},
            "end": {"dateTime": end, "timeZone": "America/New_York"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            "attachments": [
                {
                    "fileUrl": f"https://docs.google.com/document/d/{document_id}",
                    "mimeType": "application/vnd.google-apps.document",
                    "title": "Incident Document",
                }
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": "abc-123-de4",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        },
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    assert not mock_convert_string_to_camel_case.called


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_with_kwargs(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    calendar_client,
):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {
            "dateTime": "2024-07-25T13:30:00-04:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2024-07-25T14:00:00-04:00",
            "timeZone": "America/New_York",
        },
    }
    mock_unique_id.return_value = "abc-123-de4"
    mock_convert_string_to_camel_case.side_effect = lambda x: x  # just return the same value
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = "test_document_id"
    delegated_user_email = "test_custom_email"
    body_kwargs = {
        "location": "Test Location",
        "description": "Test Description",
        "time_zone": "Magic/Time_Zone",
        "attachments": [
            {
                "fileUrl": "https://docs.google.com/document/d/test_document_id",
                "mimeType": "application/vnd.google-apps.document",
                "title": "Incident Document",
            }
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": "abc-123-de4",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    result = google_calendar.insert_event(
        start,
        end,
        emails,
        title,
        incident_document=document_id,
        body_kwargs=body_kwargs,
        delegated_user_email=delegated_user_email,
    )
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email=delegated_user_email)
    insert.assert_called_once_with(
        calendarId="primary",
        body={
            "start": {"dateTime": start, "timeZone": "Magic/Time_Zone"},
            "end": {"dateTime": end, "timeZone": "Magic/Time_Zone"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            **body_kwargs,
        },
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    for key in body_kwargs:
        mock_convert_string_to_camel_case.assert_any_call(key)


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_with_no_document(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    calendar_client,
):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {
            "dateTime": "2024-07-25T13:30:00-04:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2024-07-25T14:00:00-04:00",
            "timeZone": "America/New_York",
        },
    }
    mock_unique_id.return_value = "abc-123-de4"
    mock_convert_string_to_camel_case.side_effect = lambda x: x  # just return the same value
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = ""
    delegated_user_email = "test_custom_email"
    body_kwargs = {
        "location": "Test Location",
        "description": "Test Description",
        "time_zone": "Magic/Time_Zone",
        "conferenceData": {
            "createRequest": {
                "requestId": "abc-123-de4",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    result = google_calendar.insert_event(
        start,
        end,
        emails,
        title,
        incident_document=document_id,
        body_kwargs=body_kwargs,
        delegated_user_email=delegated_user_email,
    )
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email=delegated_user_email)
    insert.assert_called_once_with(
        calendarId="primary",
        body={
            "start": {"dateTime": start, "timeZone": "Magic/Time_Zone"},
            "end": {"dateTime": end, "timeZone": "Magic/Time_Zone"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            **body_kwargs,
        },
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    for key in body_kwargs:
        mock_convert_string_to_camel_case.assert_any_call(key)


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_google_hangout_link_created(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    calendar_client,
):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {
            "dateTime": "2024-07-25T13:30:00-04:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2024-07-25T14:00:00-04:00",
            "timeZone": "America/New_York",
        },
    }
    mock_unique_id.return_value = "abc-123-de4"
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = "test_document_id"

    result = google_calendar.insert_event(start, end, emails, title, incident_document=document_id)
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    insert.assert_called_once_with(
        calendarId="primary",
        body={
            "start": {"dateTime": start, "timeZone": "America/New_York"},
            "end": {"dateTime": end, "timeZone": "America/New_York"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            "attachments": [
                {
                    "fileUrl": f"https://docs.google.com/document/d/{document_id}",
                    "mimeType": "application/vnd.google-apps.document",
                    "title": "Incident Document",
                }
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": "abc-123-de4",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        },
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    assert mock_unique_id.called
    sent_body = insert.call_args.kwargs["body"]
    assert sent_body["conferenceData"]["createRequest"]["requestId"] == mock_unique_id.return_value


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
def test_insert_event_propagates_http_error(mock_convert_string_to_camel_case, calendar_client):
    error = _http_error(500)
    calendar_client.service.events.return_value.insert.return_value.execute.side_effect = error
    start = datetime.now()

    with pytest.raises(HttpError) as exc_info:
        google_calendar.insert_event(start, start, ["test1@test.com"], "Test Event", "test_document_id")

    assert exc_info.value is error
    assert not mock_convert_string_to_camel_case.called


@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
def test_insert_event_propagates_unclassified_error(mock_convert_string_to_camel_case, calendar_client):
    error = RuntimeError("API call error")
    calendar_client.service.events.return_value.insert.return_value.execute.side_effect = error
    start = datetime.now()

    with pytest.raises(RuntimeError) as exc_info:
        google_calendar.insert_event(start, start, ["test1@test.com"], "Test Event", "test_document_id")

    assert exc_info.value is error
    assert not mock_convert_string_to_camel_case.called
