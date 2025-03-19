"""Unit tests for schedule_retro module in Incident management process."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import pytest
import pytz  # type: ignore

# from integrations.google_workspace import google_calendar
from modules.incident import schedule_retro


# Fixture to mock the event details JSON string
@pytest.fixture
def event_details():
    return json.dumps(
        {
            "emails": ["user1@example.com", "user2@example.com"],
            "topic": "Incident Response Meeting",
            "name": "Incident 123",
            "channel_id": "C123456",
            "incident_document": "https://docs.google.com/document/d/1/edit",
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
    event_details: str,
    mock_datetime_now: MagicMock | AsyncMock,  # add this fixture
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    find_first_available_slot_mock.return_value = (
        mock_datetime_now.now,  # use the fixture here
        mock_datetime_now.now + timedelta(hours=1),
    )
    insert_event_mock.return_value = {
        "event_link": "https://calendar.link",
        "event_info": "Retro has been scheduled for Monday, April 10, 2023 at 10:00 AM EDT. Check your calendar for more details.",
    }
    mock_days = 1
    mock_emails = ["user1@example.com", "user2@example.com"]

    # Parse event details
    event_details_dict = json.loads(event_details)
    emails = event_details_dict["emails"]
    name = event_details_dict["name"]
    document_id = event_details_dict["incident_document"]

    # Call the function under test
    result = schedule_retro.schedule_event(event_details, mock_days, mock_emails)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    insert_event_mock.assert_called_once_with(
        find_first_available_slot_mock.return_value[0].isoformat(),
        find_first_available_slot_mock.return_value[1].isoformat(),
        emails,
        "Retro " + name,
        document_id,
        description="This is a retro meeting to discuss incident: " + name,
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

    assert result["event_link"] == "https://calendar.link"
    assert (
        result["event_info"]
        == "Retro has been scheduled for Monday, April 10, 2023 at 10:00 AM EDT. Check your calendar for more details."
    )


# Test out the schedule_event function when no available slots are found
@patch("modules.incident.schedule_retro.get_freebusy")
@patch("modules.incident.schedule_retro.find_first_available_slot")
@patch("modules.incident.schedule_retro.insert_event")
def test_schedule_event_no_available_slots(
    insert_event_mock,
    find_first_available_slot_mock,
    get_freebusy_mock,
    event_details: str,
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    find_first_available_slot_mock.return_value = (None, None)
    mock_days = 1
    mock_emails = ["test1@test.com", "test2@test.com"]

    # Call the function under test
    event_link = schedule_retro.schedule_event(event_details, mock_days, mock_emails)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    insert_event_mock.assert_not_called()

    assert event_link is None


@patch("modules.incident.schedule_retro.slack_channels")
@patch("modules.incident.schedule_retro.incident_conversation")
def test_open_incident_retro_modal_not_incident_channel_exception(
    mock_incident_conversation,
    mock_slack_channels,
):
    mock_ack = MagicMock()
    mock_client = MagicMock()
    mock_logger = MagicMock()
    mock_incident_conversation.is_incident_channel.return_value = [False, False]

    # The test channel and user IDs
    channel_id = "C12345"
    user_id = "U12345"
    channel_name = "general"  # Not an incident channel

    # Prepare the request body
    body = {"channel_id": channel_id, "user_id": user_id, "channel_name": channel_name}

    # Call the function being tested
    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack, mock_logger)

    # Ensure the ack method was called
    mock_ack.assert_called_once()
    mock_client.conversations_members.assert_not_called()
    mock_incident_conversation.get_incident_document_id.assert_not_called()
    mock_slack_channels.fetch_user_details.assert_not_called()


def test_open_incident_retro_modal_with_no_users():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {
        "channel": {
            "topic": {"value": "Retro Topic"},
            "purpose": {"value": "Retro Purpose"},
        }
    }
    mock_client.users_info.side_effect = []
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    # Adjust the mock to simulate no users in the channel
    mock_client.conversations_members.return_value = {"members": []}

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack)

    # construct the expected data object
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_open_incident_retro_modal_with_no_topic():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {
        "channel": {"topic": {"value": ""}, "purpose": {"value": "Retro Purpose"}}
    }
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }
    mock_client.users_info.side_effect = []

    # Adjust the mock to simulate no users in the channel
    mock_client.conversations_members.return_value = {"members": []}

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack)

    # construct the expected data object and set the topic to a default one
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_open_incident_retro_modal_with_no_name():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {
        "channel": {
            "name": "",
            "topic": {"value": ""},
            "purpose": {"value": "Retro Purpose"},
        }
    }
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }
    mock_client.users_info.side_effect = []

    # Adjust the mock to simulate no users in the channel
    mock_client.conversations_members.return_value = {"members": []}

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-",
        "user_id": "U12345",
    }

    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack)

    # construct the expected data object and set the topic to a default one
    expected_data = json.dumps(
        {
            "name": "incident-",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_open_incident_retro_modal_with_no_purpose():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {
        "channel": {"topic": {"value": ""}, "purpose": {"value": ""}}
    }
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }
    mock_client.users_info.side_effect = []

    # Adjust the mock to simulate no users in the channel
    mock_client.conversations_members.return_value = {"members": []}

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack)

    # construct the expected data object and set the topic to a default one
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


@patch("modules.incident.schedule_retro.schedule_event")
def test_save_incident_retro_success(schedule_event_mock):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = {
        "event_link": "http://example.com/event",
        "event_info": "event_info",
    }
    body_mock = {"trigger_id": "some_trigger_id"}
    data_to_send = json.dumps(
        {
            "emails": [],
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    view_mock_with_link = {
        "private_metadata": data_to_send,
        "state": {
            "values": {
                "number_of_days": {"number_of_days": {"value": "1"}},
                "user_select_block": {
                    "user_select_action": {
                        "selected_options": [
                            {"value": "U0123456789"},
                            {"value": "U9876543210"},
                        ]
                    }
                },
            }
        },
    }

    # Call the function
    schedule_retro.save_incident_retro(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened
    mock_client.views_update.assert_called_once()  # Ensure the modal was updated

    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: *Scheduling the retro...*"
    )
    # Verify the modal content for success message is updated
    assert (
        mock_client.views_update.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Successfully scheduled calender event!*"
    )


@patch("modules.incident.schedule_retro.schedule_event")
def test_save_incident_retro_success_post_message_to_channel(schedule_event_mock):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = {
        "event_link": "http://example.com/event",
        "event_info": "event_info",
    }
    body_mock = {"trigger_id": "some_trigger_id"}
    data_to_send = json.dumps(
        {
            "emails": [],
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    view_mock_with_link = {
        "private_metadata": data_to_send,
        "state": {
            "values": {
                "number_of_days": {"number_of_days": {"value": "1"}},
                "user_select_block": {
                    "user_select_action": {
                        "selected_options": [
                            {"value": "U0123456789"},
                            {"value": "U9876543210"},
                        ]
                    }
                },
            }
        },
    }

    # Call the function
    schedule_retro.save_incident_retro(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened

    # Verify that the chat message was sent to the channel
    mock_client.chat_postMessage.assert_called_once()
    mock_client.chat_postMessage.assert_any_call(
        channel="C1234567890", text="event_info", unfurl_links=False
    )

    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: *Scheduling the retro...*"
    )
    # Verify the modal content for success
    assert (
        mock_client.views_update.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Successfully scheduled calender event!*"
    )


@patch("modules.incident.schedule_retro.schedule_event")
def test_save_incident_retro_failure(schedule_event_mock):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = None
    body_mock = {"trigger_id": "some_trigger_id"}
    data_to_send = json.dumps(
        {
            "emails": [],
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    view_mock_with_link = {
        "private_metadata": data_to_send,
        "state": {
            "values": {
                "number_of_days": {"number_of_days": {"value": "1"}},
                "user_select_block": {
                    "user_select_action": {
                        "selected_options": [
                            {"value": "U0123456789"},
                            {"value": "U9876543210"},
                        ]
                    }
                },
            }
        },
    }

    # Call the function
    schedule_retro.save_incident_retro(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened
    mock_client.views_update.assert_called_once()

    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: *Scheduling the retro...*"
    )
    # Verify the modal content for success
    assert (
        mock_client.views_update.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Could not schedule event - no free time was found!*"
    )


@patch("modules.incident.schedule_retro.logging")
def test_confirm_click(mock_logging):
    ack = MagicMock()
    body = {
        "user": {"id": "user_id", "username": "username"},
    }
    schedule_retro.confirm_click(ack, body, client=MagicMock())
    ack.assert_called_once()
    mock_logging.info.assert_called_once_with(
        "User username viewed the calendar event."
    )
