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
    body = {
        "trigger_id": "trigger_id",
        "channel_id": channel_id,
        "user_id": user_id,
        "channel_name": channel_name,
    }

    # Call the function being tested
    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack, mock_logger)

    # Ensure the ack method was called
    mock_ack.assert_called_once()
    mock_incident_conversation.get_incident_document_id.assert_not_called()
    mock_slack_channels.fetch_user_details.assert_not_called()
    mock_client.views_open.assert_not_called()


@patch("modules.incident.schedule_retro.generate_retro_options_view")
@patch("modules.incident.schedule_retro.slack_channels")
@patch("modules.incident.schedule_retro.incident_conversation")
def test_open_incident_retro_modal(
    mock_incident_conversation,
    mock_slack_channels,
    mock_generate_retro_options_view,
):
    mock_ack = MagicMock()
    mock_client = MagicMock()
    mock_logger = MagicMock()
    mock_incident_conversation.is_incident_channel.return_value = [True, False]
    mock_incident_conversation.get_incident_document_id.return_value = (
        "dummy_document_id"
    )
    # The test channel and user IDs
    channel_id = "C12345"
    channel_name = "incident-some-channel-name"
    user_id = "U12345"

    # Prepare the request body
    body = {
        "trigger_id": "trigger_id",
        "channel_id": channel_id,
        "user_id": user_id,
        "channel_name": channel_name,
    }
    users_details = [
        {
            "text": {
                "type": "plain_text",
                "text": "User 1",
                "emoji": True,
            },
            "value": "U0123456789",
        },
        {
            "text": {
                "type": "plain_text",
                "text": "User 2",
                "emoji": True,
            },
            "value": "U9876543210",
        },
    ]
    mock_slack_channels.fetch_user_details.return_value = users_details
    mocked_view = {
        "type": "modal",
        "callback_id": "schedule_retro",
    }
    mock_generate_retro_options_view.return_value = mocked_view
    metadata_json = json.dumps(
        {
            "name": channel_name,
            "incident_document": "dummy_document_id",
            "channel_id": channel_id,
        }
    )
    # Call the function being tested
    schedule_retro.open_incident_retro_modal(mock_client, body, mock_ack, mock_logger)

    mock_ack.assert_called_once()
    mock_incident_conversation.get_incident_document_id.assert_called_once_with(
        mock_client,
        channel_id,
        mock_logger,
    )
    mock_slack_channels.fetch_user_details.assert_called_once_with(
        mock_client, channel_id
    )
    mock_generate_retro_options_view.assert_called_once_with(
        metadata_json, users_details
    )
    mock_client.views_open.assert_called_once_with(
        trigger_id="trigger_id",
        view=mock_generate_retro_options_view.return_value,
    )


def test_generate_retro_options_view_no_unavailable_users():
    """Test that the modal is correctly generated with no unavailable users."""
    # Setup
    private_metadata = json.dumps(
        {
            "name": "incident-test-channel",
            "incident_document": "test-doc-id",
            "channel_id": "C12345",
        }
    )

    all_users = [
        {
            "text": {
                "type": "plain_text",
                "text": "User 1",
                "emoji": True,
            },
            "value": "U0123456789",
        },
        {
            "text": {
                "type": "plain_text",
                "text": "User 2",
                "emoji": True,
            },
            "value": "U9876543210",
        },
    ]

    # Call the function
    result = schedule_retro.generate_retro_options_view(private_metadata, all_users)

    # Assertions
    assert result["type"] == "modal"
    assert result["callback_id"] == "view_save_event"
    assert result["private_metadata"] == private_metadata
    assert result["submit"]["text"] == "Schedule"
    assert result["submit_disabled"] is False

    # Check blocks - there should be exactly 7 blocks (2 top blocks + divider + 5 rule blocks)
    assert len(result["blocks"]) == 8

    # Verify the blocks structure
    assert result["blocks"][0]["type"] == "input"  # Days input
    assert result["blocks"][1]["type"] == "section"  # User select
    assert result["blocks"][2]["type"] == "divider"  # Divider

    # Verify no unavailable users block
    for block in result["blocks"]:
        if block["type"] == "section" and "text" in block:
            text = block["text"].get("text", "")
            assert "calendar availability issues" not in text


def test_generate_retro_options_view_with_unavailable_users():
    """Test that the modal is correctly generated with unavailable users."""
    # Setup
    private_metadata = json.dumps(
        {
            "name": "incident-test-channel",
            "incident_document": "test-doc-id",
            "channel_id": "C12345",
        }
    )

    all_users = [
        {
            "text": {
                "type": "plain_text",
                "text": "User 1",
                "emoji": True,
            },
            "value": "U0123456789",
        },
        {
            "text": {
                "type": "plain_text",
                "text": "User 2",
                "emoji": True,
            },
            "value": "U9876543210",
        },
    ]

    unavailable_users = ["user1@example.com", "user2@example.com"]

    # Call the function
    result = schedule_retro.generate_retro_options_view(
        private_metadata, all_users, unavailable_users
    )

    # Assertions
    assert result["type"] == "modal"
    assert result["callback_id"] == "view_save_event"
    assert result["private_metadata"] == private_metadata
    assert result["submit"]["text"] == "Schedule"
    assert result["submit_disabled"] is False

    # Check blocks - there should be exactly 9 blocks (2 top blocks + unavailable users block + divider + 5 rule blocks)
    assert len(result["blocks"]) == 9

    # Verify the blocks structure
    assert result["blocks"][0]["type"] == "input"  # Days input
    assert result["blocks"][1]["type"] == "section"  # User select

    # Verify unavailable users block exists and has the correct content
    assert result["blocks"][2]["type"] == "section"
    assert "calendar availability issues" in result["blocks"][2]["text"]["text"]
    assert "user1@example.com" in result["blocks"][2]["text"]["text"]
    assert "user2@example.com" in result["blocks"][2]["text"]["text"]

    # Verify divider and rules follow
    assert result["blocks"][3]["type"] == "divider"


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
