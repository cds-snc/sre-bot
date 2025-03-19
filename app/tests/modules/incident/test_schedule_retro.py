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
@patch("modules.incident.schedule_retro.identify_unavailable_users")
@patch("modules.incident.schedule_retro.get_freebusy")
@patch("modules.incident.schedule_retro.find_first_available_slot")
def test_schedule_event_successful(
    find_first_available_slot_mock,
    get_freebusy_mock,
    identifiy_unavailable_users_mock,
    mock_datetime_now: MagicMock | AsyncMock,  # add this fixture
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    identifiy_unavailable_users_mock.return_value = []
    start = mock_datetime_now.now
    end = mock_datetime_now.now + timedelta(hours=1)
    find_first_available_slot_mock.return_value = (
        start,
        end,
    )
    mock_days = 1
    mock_users = [
        {
            "text": {"type": "plain_text", "text": "User 1", "emoji": True},
            "value": "U1",
        },
        {
            "text": {"type": "plain_text", "text": "User 2", "emoji": True},
            "value": "U2",
        },
    ]
    mock_client = MagicMock()
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user1@example.com"}}},
        {"user": {"profile": {"email": "user2@example.com"}}},
    ]
    # Call the function under test
    result = schedule_retro.schedule_event(mock_client, mock_days, mock_users)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    assert result["first_available_start"] == start
    assert result["first_available_end"] == end
    assert result["unavailable_users"] == []


# Test out the schedule_event function when no available slots are found
@patch("modules.incident.schedule_retro.logging")
@patch("modules.incident.schedule_retro.identify_unavailable_users")
@patch("modules.incident.schedule_retro.get_freebusy")
@patch("modules.incident.schedule_retro.find_first_available_slot")
def test_schedule_event_no_available_slots(
    find_first_available_slot_mock,
    get_freebusy_mock,
    identifiy_unavailable_users_mock,
    logging_mock,
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {"result": "Mocked FreeBusy Query Result"}
    find_first_available_slot_mock.return_value = (None, None)
    mock_days = 1
    mock_users = [
        {
            "text": {"type": "plain_text", "text": "User 1", "emoji": True},
            "value": "U1",
        },
        {
            "text": {"type": "plain_text", "text": "User 2", "emoji": True},
            "value": "U2",
        },
    ]
    mock_client = MagicMock()
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user1@example.com"}}},
        {"user": {"profile": {"email": "user2@example.com"}}},
    ]
    mock_emails = ["user1@example.com", "user2@example.com"]
    identifiy_unavailable_users_mock.return_value = mock_emails

    # Call the function under test
    result = schedule_retro.schedule_event(mock_client, mock_days, mock_users)

    # Assertions
    get_freebusy_mock.assert_called_once()
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    logging_mock.warning.assert_called_once()
    assert result["first_available_start"] is None
    assert result["first_available_end"] is None
    assert result["unavailable_users"] == mock_emails


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


@patch("modules.incident.schedule_retro.save_retro_event")
@patch("modules.incident.schedule_retro.schedule_event")
def test_handle_schedule_retro_submit_success(
    schedule_event_mock, save_retro_event_mock
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = {
        "first_available_start": "2023-04-10T10:00:00-04:00",
        "first_available_end": "2023-04-10T10:30:00-04:00",
        "unavailable_users": [],
    }
    save_retro_event_mock.return_value = {
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
    schedule_retro.handle_schedule_retro_submit(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened
    mock_client.views_update.assert_called_once()  # Ensure the modal was updated

    # Verify that the chat message was sent to the channel
    mock_client.chat_postMessage.assert_called_once()
    mock_client.chat_postMessage.assert_any_call(
        channel="C1234567890", text="event_info", unfurl_links=False
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: *Scheduling the retro...*"
    )
    # Verify the modal content for success message is updated
    assert (
        mock_client.views_update.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Successfully scheduled calender event!*"
    )


@patch("modules.incident.schedule_retro.save_retro_event")
@patch("modules.incident.schedule_retro.schedule_event")
def test_handle_schedule_retro_submit_no_time_found(
    schedule_event_mock, save_retro_event_mock
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = {
        "first_available_start": None,
        "first_available_end": None,
        "unavailable_users": [],
    }
    save_retro_event_mock.return_value = None

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
    schedule_retro.handle_schedule_retro_submit(
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
    save_retro_event_mock.assert_not_called()


@patch("modules.incident.schedule_retro.save_retro_event")
@patch("modules.incident.schedule_retro.schedule_event")
def test_handle_schedule_retro_submit_save_failed(
    schedule_event_mock, save_retro_event_mock
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = {
        "first_available_start": "2023-04-10T10:00:00-04:00",
        "first_available_end": "2023-04-10T10:30:00-04:00",
        "unavailable_users": [],
    }
    save_retro_event_mock.return_value = None

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
    schedule_retro.handle_schedule_retro_submit(
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


@patch("modules.incident.schedule_retro.insert_event")
def test_save_retro_event(
    mock_insert_event,
    mock_datetime_now: MagicMock | AsyncMock,  # add this fixture
):
    first_available_start = mock_datetime_now.now
    first_available_end = mock_datetime_now.now + timedelta(hours=1)
    user_emails = ["email1", "email2"]
    incident_name = "incident-2024-01-12-test"
    incident_document = "dummy_document_id"

    mock_insert_event.return_value = {
        "event_link": "http://example.com/event",
        "event_info": "Incident Response Meeting",
    }
    # Call the function
    result = schedule_retro.save_retro_event(
        first_available_start,
        first_available_end,
        user_emails,
        incident_name,
        incident_document,
    )
    mock_insert_event.assert_called_once()
    assert result == {
        "event_link": "http://example.com/event",
        "event_info": "Incident Response Meeting",
    }


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


def test_get_users_emails_from_selected_options():
    # Setup a fake client that returns user info with an email
    mock_client = MagicMock()
    mock_client.users_info.return_value = {
        "user": {"profile": {"email": "test@example.com"}}
    }
    selected_options = [{"value": " U1 "}, {"value": " U2 "}]
    # For second call, change the fake response
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "test1@example.com"}}},
        {"user": {"profile": {"email": "test2@example.com"}}},
    ]

    emails = schedule_retro.get_users_emails_from_selected_options(
        mock_client, selected_options
    )
    assert emails == ["test1@example.com", "test2@example.com"]


@patch("modules.incident.schedule_retro.schedule_event")
@patch("modules.incident.schedule_retro.generate_retro_options_view")
def test_incident_selected_users_updated_empty(
    mock_generate_retro_options_view,
    mock_schedule_event,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_generate_retro_options_view.return_value = {"dummy": "view"}
    dummy_users = [
        {
            "text": {"type": "plain_text", "text": "User 1", "emoji": True},
            "value": "U1",
        },
        {
            "text": {"type": "plain_text", "text": "User 2", "emoji": True},
            "value": "U2",
        },
    ]
    body = {
        "view": {
            "id": "VIEW456",
            "private_metadata": json.dumps(
                {"channel_id": "C67890", "name": "incident-test"}
            ),
            "blocks": [
                {
                    "block_id": "number_of_days",
                    "element": {"value": "1"},
                },
                {
                    "block_id": "user_select_block",
                    "accessory": {"type": "multi_users_select", "options": dummy_users},
                },
            ],
        },
        "actions": [{"selected_options": []}],
    }
    # Call the function; since selected users list is empty, it should return without further calls.
    schedule_retro.incident_selected_users_updated(mock_client, body, mock_ack)
    mock_ack.assert_called_once()
    mock_client.views_update.assert_called_once_with(
        view_id="VIEW456", view={"dummy": "view"}
    )
    mock_schedule_event.assert_not_called()
    mock_client.users_lookupByEmail.assert_not_called()


@patch("modules.incident.schedule_retro.generate_retro_options_view")
@patch("modules.incident.schedule_retro.schedule_event")
def test_incident_selected_users_updated_with_users(
    mock_schedule_event,
    mock_generate_retro_options_view,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    # Prepare body with selected options (non-empty)
    dummy_users = [
        {
            "text": {"type": "plain_text", "text": "User 1", "emoji": True},
            "value": "U1",
        },
        {
            "text": {"type": "plain_text", "text": "User 2", "emoji": True},
            "value": "U2",
        },
    ]
    body = {
        "view": {
            "id": "VIEW456",
            "private_metadata": json.dumps(
                {"channel_id": "C67890", "name": "incident-test"}
            ),
            "blocks": [
                {
                    "block_id": "number_of_days",
                    "element": {"value": "1"},
                },
                {
                    "block_id": "user_select_block",
                    "accessory": {"type": "multi_users_select", "options": dummy_users},
                },
            ],
        },
        "actions": [{"selected_options": [dummy_users[0]]}],
    }
    # schedule_event returns unavailable users
    mock_schedule_event.return_value = {"unavailable_users": ["user2@example.com"]}
    # slack_channels.fetch_user_details returns a dummy user details list
    # generate_retro_options_view returns a dummy view
    dummy_view = {"dummy": "view"}
    mock_generate_view = mock_generate_retro_options_view
    mock_generate_view.return_value = dummy_view

    # Call the function
    schedule_retro.incident_selected_users_updated(mock_client, body, mock_ack)

    mock_ack.assert_called_once()
    mock_schedule_event.assert_called_once_with(mock_client, 1, [dummy_users[0]])

    mock_generate_view.assert_called_once()
    mock_client.views_update.assert_called_once_with(view_id="VIEW456", view=dummy_view)
