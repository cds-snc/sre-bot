"""Unit tests for schedule_retro module in Incident management proces."""

import json
from unittest.mock import patch
from datetime import datetime, timedelta
import pytest
import pytz

# from integrations.google_workspace import google_calendar
from modules.incident import schedule_retro


# Fixture to mock the event details JSON string
@pytest.fixture
def event_details():
    return json.dumps(
        {
            "emails": ["user1@example.com", "user2@example.com"],
            "topic": "Incident Response Meeting",
        }
    )


# Fixture to mock the timezone
@pytest.fixture
def est_timezone():
    return pytz.timezone("US/Eastern")


# Fixture to mock the datetime.now() function
@pytest.fixture
def mock_datetime_now(est_timezone):
    """Fixture to mock datetime.now() to return a specific time in the EST timezone."""
    # Mocking the specific date we want to consider as "now"
    specific_now = datetime(
        2023, 4, 10, 10, 0, tzinfo=est_timezone
    )  # Assuming April 10, 2023, is a Monday

    with patch("modules.incident.schedule_retro.datetime") as mock_datetime:
        mock_datetime.now.return_value = specific_now
        mock_datetime.strptime.side_effect = lambda *args, **kw: datetime.strptime(
            *args, **kw
        )
        yield mock_datetime


# Test out the schedule_event function is successful
@patch("modules.incident.schedule_retro.get_freebusy")
@patch("modules.incident.schedule_retro.find_first_available_slot")
@patch("modules.incident.schedule_retro.insert_event")
def test_schedule_event_successful(
    insert_event_mock,
    find_first_available_slot_mock,
    get_freebusy_mock,
    event_details,
    mock_datetime_now,  # add this fixture
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    find_first_available_slot_mock.return_value = (
        mock_datetime_now.now,  # use the fixture here
        mock_datetime_now.now + timedelta(hours=1),
    )
    insert_event_mock.return_value = "https://calendar.link"
    mock_days = 1

    # Parse event details
    event_details_dict = json.loads(event_details)
    emails = event_details_dict["emails"]
    topic = event_details_dict["topic"]

    # Call the function under test
    event_link = schedule_retro.schedule_event(event_details, mock_days)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    insert_event_mock.assert_called_once_with(
        find_first_available_slot_mock.return_value[0].isoformat(),
        find_first_available_slot_mock.return_value[1].isoformat(),
        emails,
        "Retro " + topic,
        description="This is a retro meeting to discuss incident: " + topic,
        conferenceData={
            "createRequest": {
                "requestId": f"{find_first_available_slot_mock.return_value[0].timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        reminders={
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
            ],
        },
    )

    assert event_link == "https://calendar.link"


# Test out the schedule_event function when no available slots are found
@patch("modules.incident.schedule_retro.get_freebusy")
@patch("modules.incident.schedule_retro.find_first_available_slot")
@patch("modules.incident.schedule_retro.insert_event")
def test_schedule_event_no_available_slots(
    insert_event_mock,
    find_first_available_slot_mock,
    get_freebusy_mock,
    event_details,
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    find_first_available_slot_mock.return_value = (None, None)
    mock_days = 1

    # Call the function under test
    event_link = schedule_retro.schedule_event(event_details, mock_days)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    insert_event_mock.assert_not_called()

    assert event_link is None
