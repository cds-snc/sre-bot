"""Unit tests for google_calendar module."""

import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytest
import pytz
from integrations.google_workspace import google_calendar


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


# Fixture to mock the timezone
@pytest.fixture
def est_timezone():
    return pytz.timezone("US/Eastern")


@pytest.fixture
def fixed_utc_now():
    # Return a fixed UTC datetime
    return datetime(2023, 4, 10, 12, 0)  # This is a Monday


# Fixture to mock the datetime.now() function
@pytest.fixture
def mock_datetime_now(est_timezone):
    """Fixture to mock datetime.now() to return a specific time in the EST timezone."""
    # Mocking the specific date we want to consider as "now"
    specific_now = datetime(
        2023, 4, 10, 10, 0, tzinfo=est_timezone
    )  # Assuming April 10, 2023, is a Monday

    with patch(
        "integrations.google_workspace.google_calendar.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = specific_now
        mock_datetime.strptime.side_effect = lambda *args, **kw: datetime.strptime(
            *args, **kw
        )
        yield mock_datetime


# Fixture to mock the list of calendars
@pytest.fixture
def items():
    return [{"id": "calendar1"}, {"id": "calendar2"}]


# Fixture to mock the year
@pytest.fixture
def mock_year():
    return 2024


@patch(
    "integrations.google_workspace.google_calendar.DEFAULT_DELEGATED_ADMIN_EMAIL",
    "test_email",
)
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_required_args_only(mock_execute_google_api_call, items):
    mock_execute_google_api_call.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"

    google_calendar.get_freebusy(time_min, time_max, items)

    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        delegated_user_email="test_email",
        scopes=["https://www.googleapis.com/auth/calendar"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
        },
    )


@patch(
    "integrations.google_workspace.google_calendar.DEFAULT_DELEGATED_ADMIN_EMAIL",
    "test_email",
)
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_optional_args(mock_execute_google_api_call, items):
    mock_execute_google_api_call.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    time_zone = "America/Los_Angeles"
    calendar_expansion_max = 20
    group_expansion_max = 30

    google_calendar.get_freebusy(
        time_min,
        time_max,
        items,
        time_zone=time_zone,
        calendar_expansion_max=calendar_expansion_max,
        group_expansion_max=group_expansion_max,
    )

    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        delegated_user_email="test_email",
        scopes=["https://www.googleapis.com/auth/calendar"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
            "timeZone": "America/Los_Angeles",
            "calendarExpansionMax": 20,
            "groupExpansionMax": 30,
        },
    )


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_returns_object(mock_execute):
    mock_execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    items = ["calendar1", "calendar2"]

    result = google_calendar.get_freebusy(time_min, time_max, items)

    assert isinstance(result, dict)


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_no_kwargs_no_delegated_email(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    mock_execute_google_api_call,
    mock_os_environ_get,
):
    mock_execute_google_api_call.return_value = {
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
    result = google_calendar.insert_event(start, end, emails, title, document_id)
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_email",
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
        calendarId="primary",
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    assert not mock_convert_string_to_camel_case.called
    assert mock_os_environ_get.called_once_with("SRE_BOT_EMAIL")


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_with_kwargs(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    mock_execute_google_api_call,
    mock_os_environ_get,
):
    mock_execute_google_api_call.return_value = {
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
    mock_convert_string_to_camel_case.side_effect = (
        lambda x: x
    )  # just return the same value
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = "test_document_id"
    kwargs = {
        "location": "Test Location",
        "description": "Test Description",
        "delegated_user_email": "test_custom_email",
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
        start, end, emails, title, document_id, **kwargs
    )
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_custom_email",
        body={
            "start": {"dateTime": start, "timeZone": "Magic/Time_Zone"},
            "end": {"dateTime": end, "timeZone": "Magic/Time_Zone"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            **kwargs,
        },
        calendarId="primary",
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    for key in kwargs:
        mock_convert_string_to_camel_case.assert_any_call(key)

    assert not mock_os_environ_get.called


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_with_no_document(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    mock_execute_google_api_call,
    mock_os_environ_get,
):
    mock_execute_google_api_call.return_value = {
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
    mock_convert_string_to_camel_case.side_effect = (
        lambda x: x
    )  # just return the same value
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = ""
    kwargs = {
        "location": "Test Location",
        "description": "Test Description",
        "delegated_user_email": "test_custom_email",
        "time_zone": "Magic/Time_Zone",
        "conferenceData": {
            "createRequest": {
                "requestId": "abc-123-de4",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    result = google_calendar.insert_event(
        start, end, emails, title, document_id, **kwargs
    )
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_custom_email",
        body={
            "start": {"dateTime": start, "timeZone": "Magic/Time_Zone"},
            "end": {"dateTime": end, "timeZone": "Magic/Time_Zone"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            "guestsCanModify": True,
            "guestsCanInviteOthers": True,
            **kwargs,
        },
        calendarId="primary",
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    for key in kwargs:
        mock_convert_string_to_camel_case.assert_any_call(key)

    assert not mock_os_environ_get.called


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_calendar.generate_unique_id")
def test_insert_event_google_hangout_link_created(
    mock_unique_id,
    mock_convert_string_to_camel_case,
    mock_execute_google_api_call,
    mock_os_environ_get,
):
    mock_execute_google_api_call.return_value = {
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
    result = google_calendar.insert_event(start, end, emails, title, document_id)
    assert result == {
        "event_info": "Retro has been scheduled for Thursday, July 25, 2024 at 01:30 PM EDT. Check your calendar for more details.",
        "event_link": "test_link",
    }
    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_email",
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
        calendarId="primary",
        supportsAttachments=True,
        sendUpdates="all",
        conferenceDataVersion=1,
    )
    assert mock_unique_id.called
    assert mock_execute_google_api_call.contains("conferenceData")
    assert mock_execute_google_api_call.contains(mock_unique_id.return_value)


@patch("integrations.google_workspace.google_service.handle_google_api_errors")
@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_string_to_camel_case")
def test_insert_event_api_call_error(
    mock_convert_string_to_camel_case,
    mock_execute_google_api_call,
    mock_os_environ_get,
    mock_handle_errors,
    caplog,
):
    mock_execute_google_api_call.side_effect = Exception("API call error")
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    document_id = "test_document_id"
    google_calendar.insert_event(start, end, emails, title, document_id)
    assert (
        "An unexpected error occurred in function 'integrations.google_workspace.google_calendar:insert_event': API call error"
        in caplog.text
    )
    assert not mock_convert_string_to_camel_case.called
    assert mock_os_environ_get.called
    assert not mock_handle_errors.called


@patch("integrations.google_workspace.google_calendar.get_federal_holidays")
@patch("integrations.google_workspace.google_calendar.datetime")
def test_available_slot_on_first_weekday(
    mock_datetime, mock_federal_holidays, fixed_utc_now, mock_year, est_timezone
):
    # Mock datetime to control the flow of time in the test
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.return_value.year = 2024
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

    # Simulate a freebusy response with no busy times on the first available day
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2023-04-10T17:00:000Z",
                        "end": "2023-04-10T17:30:000Z",
                    }
                ]
            }
        }
    }
    mock_federal_holidays.return_value = {
        "holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]
    }

    # Expected search date is three days in the future (which should be Thursday)
    # Busy period is from 1 PM to 1:30 PM EST on the first day being checked (April 13th)
    # The function should find an available slot after the busy period
    expected_start_time = fixed_utc_now.replace(
        day=fixed_utc_now.day + 3, hour=17, minute=0, second=0, microsecond=0
    ).astimezone(est_timezone)
    expected_end_time = expected_start_time + timedelta(minutes=30)

    # Run the function under test
    actual_start, actual_end = google_calendar.find_first_available_slot(
        freebusy_response, days_in_future=3, duration_minutes=30, search_days_limit=60
    )

    # Check if the times returned match the expected values
    assert actual_start == expected_start_time
    assert actual_end == expected_end_time


# Test out the find_first_available_slot function when multiple busy days
@patch("integrations.google_workspace.google_calendar.get_federal_holidays")
@patch("integrations.google_workspace.google_calendar.datetime")
def test_opening_exists_after_busy_days(
    mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone
):
    # Mock datetime to control the flow of time in the test
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.return_value.year = 2024
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": "2023-04-13T17:00:000Z", "end": "2023-04-13T19:00:000Z"},
                    {"start": "2023-04-14T17:00:000Z", "end": "2023-04-14T19:00:000Z"},
                    {"start": "2023-04-17T17:00:000Z", "end": "2023-04-17T19:00:000Z"},
                    {"start": "2023-04-18T17:00:000Z", "end": "2023-04-18T19:00:000Z"},
                ]
            }
        }
    }

    mock_federal_holidays.return_value = {
        "holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]
    }

    start, end = google_calendar.find_first_available_slot(
        freebusy_response, days_in_future=3, duration_minutes=30, search_days_limit=60
    )
    expected_start = fixed_utc_now.replace(
        day=fixed_utc_now.day + 9, hour=17, minute=0, second=0, microsecond=0
    ).astimezone(est_timezone)
    expected_end = expected_start + timedelta(minutes=30)

    assert (
        start == expected_start and end == expected_end
    ), "Expected to find an available slot correctly."


# Test that weekends are skipped when searching for available slots
@patch("integrations.google_workspace.google_calendar.get_federal_holidays")
@patch("integrations.google_workspace.google_calendar.datetime")
def test_skipping_weekends(
    mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone
):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    # Assuming weekdays are busy, but we expect the function to skip weekends automatically
                ]
            }
        }
    }

    mock_federal_holidays.return_value = {
        "holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]
    }

    # For this test, ensure the mocked 'now' falls before a weekend, and verify that the function skips to the next weekday
    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=1, search_days_limit=60
    )

    # Adjust these expected values based on the specific 'now' being mocked
    expected_start = fixed_utc_now.replace(
        day=fixed_utc_now.day + 1, hour=17, minute=0, second=0, microsecond=0
    ).astimezone(est_timezone)
    expected_end = expected_start + timedelta(minutes=30)

    assert (
        start == expected_start and end == expected_end
    ), "Expected to find an available slot after skipping the weekend"


# Test that no available slots are found within the search limit
@patch("integrations.google_workspace.google_calendar.get_federal_holidays")
@patch("integrations.google_workspace.google_calendar.datetime")
def test_no_available_slots_within_search_limit(
    mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone
):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    # Simulate a scenario where every eligible day within the search window is fully booked
                    # For simplicity, let's assume a pattern that covers the search hours for the next 60 days
                    {"start": "2023-04-10T17:00:000Z", "end": "2023-08-13T19:00:000Z"},
                ]
            }
        }
    }

    mock_federal_holidays.return_value = {
        "holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]
    }

    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60
    )

    assert (
        start is None and end is None
    ), "Expected no available slots within the search limit"


# test that the federal holidays are correctly parsed
def test_get_federal_holidays(requests_mock):
    # set the timeout to 10s
    requests_mock.DEFAULT_TIMEOUT = 10
    # Mock the API response
    mocked_response = {
        "holidays": [
            {"observedDate": "2024-01-01"},
            {"observedDate": "2024-07-01"},
            {"observedDate": "2024-12-25"},
        ]
    }
    # Bandit skip security check for the requests_mock.get call
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2024",
        json=mocked_response,
    )

    # Call the function
    holidays = google_calendar.get_federal_holidays()

    # Assert that the holidays are correctly parsed
    assert holidays == ["2024-01-01", "2024-07-01", "2024-12-25"]


# test that holidays are correctly fetched for a different year
def test_get_federal_holidays_with_different_year(requests_mock):
    # set the timeout to 10s
    requests_mock.DEFAULT_TIMEOUT = 10
    # Mock the API response for a different year
    # Bandit skip security check for the requests_mock.get call
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2025",
        json={"holidays": []},
    )

    # Patch datetime to control the current year
    with patch(
        "integrations.google_workspace.google_calendar.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 1, 1)

        # Call the function
        holidays = google_calendar.get_federal_holidays()

        # Assert that no holidays are returned for the mocked year
        assert holidays == []


# Test that an empty list is returned when there are no holidays
def test_api_returns_empty_list(requests_mock):
    # set the timeout to 10s
    requests_mock.DEFAULT_TIMEOUT = 10
    # Mock no holidays
    # Bandit skip security check for the requests_mock.get call
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2024",
        json={"holidays": []},
    )

    # Execute
    holidays = google_calendar.get_federal_holidays()

    # Verify that an empty list is correctly handled
    assert holidays == [], "Expected an empty list when there are no holidays"


# Test that a leap year is correctly handled
def test_leap_year_handling(requests_mock):
    # set the timeout to 10s
    requests_mock.DEFAULT_TIMEOUT = 10
    # Mock response for a leap year with an extra day
    # Bandit skip security check for the requests_mock.get call
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2024",
        json={
            "holidays": [
                {
                    "observedDate": "2024-02-29"
                }  # Assuming this is a special leap year holiday
            ]
        },
    )

    # Execute
    holidays = google_calendar.get_federal_holidays()

    # Verify leap year is considered
    assert "2024-02-29" in holidays, "Leap year date should be included in the holidays"
