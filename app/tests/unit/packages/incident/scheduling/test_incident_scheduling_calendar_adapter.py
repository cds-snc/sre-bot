"""Behavior tests for the incident Calendar adapter's request boundary."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from packages.incident.scheduling.adapters import google_calendar

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
    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_calendar_service", factory)
    monkeypatch.setattr(google_calendar, "get_calendar_service", factory, raising=False)
    return SimpleNamespace(factory=factory, service=service)


def test_get_freebusy_calls_calendar_resource_with_required_body(calendar_client):
    query = calendar_client.service.freebusy.return_value.query
    query.return_value.execute.return_value = {"calendars": {}}

    result = google_calendar.get_freebusy(
        "2022-01-01T00:00:00Z",
        "2022-01-02T00:00:00Z",
        [{"id": "calendar1"}],
    )

    assert result == {"calendars": {}}
    calendar_client.factory.assert_called_once_with(scopes=CALENDAR_SCOPES, delegated_user_email=None)
    query.assert_called_once_with(
        body={
            "timeMin": "2022-01-01T00:00:00Z",
            "timeMax": "2022-01-02T00:00:00Z",
            "items": [{"id": "calendar1"}],
        }
    )
    query.return_value.execute.assert_called_once_with()


def test_get_freebusy_passes_optional_body_and_delegated_user(calendar_client):
    query = calendar_client.service.freebusy.return_value.query
    query.return_value.execute.return_value = {}

    google_calendar.get_freebusy(
        "2022-01-01T00:00:00Z",
        "2022-01-02T00:00:00Z",
        ["calendar1"],
        body_kwargs={"time_zone": "America/Los_Angeles", "groupExpansionMax": 30},
        delegated_user_email="custom@example.com",
    )

    calendar_client.factory.assert_called_once_with(
        scopes=CALENDAR_SCOPES,
        delegated_user_email="custom@example.com",
    )
    assert query.call_args.kwargs["body"] == {
        "timeMin": "2022-01-01T00:00:00Z",
        "timeMax": "2022-01-02T00:00:00Z",
        "items": ["calendar1"],
        "timeZone": "America/Los_Angeles",
        "groupExpansionMax": 30,
    }


def test_get_freebusy_propagates_http_error(calendar_client):
    error = _http_error(429)
    calendar_client.service.freebusy.return_value.query.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_calendar.get_freebusy("2022-01-01T00:00:00Z", "2022-01-02T00:00:00Z", [])

    assert exc_info.value is error


@patch("packages.incident.scheduling.adapters.google_calendar.generate_unique_id")
@patch("packages.incident.scheduling.adapters.google_calendar.convert_string_to_camel_case")
def test_insert_event_builds_event_and_returns_link(
    mock_convert,
    mock_unique_id,
    calendar_client,
):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {"dateTime": "2024-07-25T13:30:00-04:00"},
    }
    mock_unique_id.return_value = "abc-123-de4"
    mock_convert.side_effect = lambda value: value
    start = datetime.now()

    result = google_calendar.insert_event(
        start,
        start,
        [" test1@test.com "],
        "Test Event",
        incident_document="test_document_id",
        body_kwargs={"location": "Test Location", "time_zone": "America/New_York"},
        delegated_user_email="custom@example.com",
    )

    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    calendar_client.factory.assert_called_once_with(
        scopes=CALENDAR_SCOPES,
        delegated_user_email="custom@example.com",
    )
    insert.assert_called_once_with(
        calendarId="primary",
        body={
            "start": {"dateTime": start, "timeZone": "America/New_York"},
            "end": {"dateTime": start, "timeZone": "America/New_York"},
            "attendees": [{"email": "test1@test.com"}],
            "summary": "Test Event",
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
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
            "location": "Test Location",
            "time_zone": "America/New_York",
        },
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )


def test_insert_event_without_document_omits_attachment(calendar_client):
    insert = calendar_client.service.events.return_value.insert
    insert.return_value.execute.return_value = {
        "htmlLink": "test_link",
        "start": {"dateTime": "2024-07-25T13:30:00-04:00"},
    }

    google_calendar.insert_event(datetime.now(), datetime.now(), ["test@example.com"], "Test Event")

    assert "attachments" not in insert.call_args.kwargs["body"]


@patch("packages.incident.scheduling.adapters.google_calendar.convert_string_to_camel_case")
def test_insert_event_propagates_http_error(mock_convert, calendar_client):
    error = _http_error(500)
    calendar_client.service.events.return_value.insert.return_value.execute.side_effect = error
    start = datetime.now()

    with pytest.raises(HttpError) as exc_info:
        google_calendar.insert_event(start, start, ["test@example.com"], "Test Event", "document")

    assert exc_info.value is error
    assert not mock_convert.called


@patch("packages.incident.scheduling.adapters.google_calendar.convert_string_to_camel_case")
def test_insert_event_propagates_unclassified_error(mock_convert, calendar_client):
    error = RuntimeError("API call error")
    calendar_client.service.events.return_value.insert.return_value.execute.side_effect = error
    start = datetime.now()

    with pytest.raises(RuntimeError) as exc_info:
        google_calendar.insert_event(start, start, ["test@example.com"], "Test Event", "document")

    assert exc_info.value is error
    assert not mock_convert.called


def test_get_freebusy_classifies_and_logs_http_error(calendar_client, monkeypatch):
    error = _http_error(429)
    calendar_client.service.freebusy.return_value.query.return_value.execute.side_effect = error
    classify = MagicMock(return_value=(SimpleNamespace(value="transient_error"), "429", 7))
    warning = MagicMock()
    monkeypatch.setattr(google_calendar, "classify_google_error", classify)
    monkeypatch.setattr(google_calendar.logger, "warning", warning)

    with pytest.raises(HttpError):
        google_calendar.get_freebusy("2022-01-01T00:00:00Z", "2022-01-02T00:00:00Z", [])

    classify.assert_called_once_with(error)
    warning.assert_called_once_with(
        "google_api_request_failed",
        status="transient_error",
        error_code="429",
        retry_after=7,
    )
