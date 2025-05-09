import json
import uuid
from unittest.mock import ANY, MagicMock, patch
import pytest

from modules import incident_helper


@patch("modules.incident.incident_helper.incident_conversation")
@patch("modules.incident.incident_helper.information_display.open_incident_info_view")
def test_handle_incident_command_with_empty_args(
    mock_open_incident_info_view, mock_incident_conversation
):
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    body = {
        "channel_id": "channel_id",
    }
    mock_incident_conversation.is_incident_channel.return_value = (True, False)
    incident_helper.handle_incident_command([], client, body, respond, ack)
    mock_open_incident_info_view.assert_called_once_with(client, body, respond)


@patch("modules.incident.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command(create_folder_mock):
    create_folder_mock.return_value = {"id": "test_id", "name": "foo bar"}
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with("Folder `foo bar` created.")


@patch("modules.incident.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command_error(create_folder_mock):
    create_folder_mock.return_value = None
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with("Failed to create folder `foo bar`.")


def test_handle_incident_command_with_help():
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(
        ["help"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with(incident_helper.help_text)


@patch("modules.incident.incident_helper.incident_folder.list_folders_view")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(
        ["list-folders"], client, body, respond, ack
    )
    list_folders_mock.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.incident_roles.manage_roles")
def test_handle_incident_command_with_roles(manage_roles_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["roles"], client, body, respond, ack)
    manage_roles_mock.assert_called_once_with(client, body, ack, respond)


@patch("modules.incident.incident_helper.close_incident")
def test_handle_incident_command_with_close(close_incident_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["close"], client, body, respond, ack)
    close_incident_mock.assert_called_once_with(client, body, ack, respond)


@patch("modules.incident.incident_helper.stale_incidents")
def test_handle_incident_command_with_stale(stale_incidents_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["stale"], client, body, respond, ack)
    stale_incidents_mock.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.schedule_retro")
def test_handle_incident_command_with_retro(schedule_retro_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["schedule"], client, body, respond, ack)
    schedule_retro_mock.open_incident_retro_modal.assert_called_once_with(
        client, body, ack
    )


@patch("modules.incident.incident_helper.handle_update_status_command")
def test_handle_incident_command_with_update_status_command(
    mock_handle_update_status_command,
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    args = ["status", "Ready", "to", "be", "Reviewed"]
    incident_helper.handle_incident_command(args, client, body, respond, ack)
    args.pop(0)
    mock_handle_update_status_command.assert_called_once_with(
        client, body, respond, ack, args
    )


@patch("modules.incident.incident_helper.open_updates_dialog")
def test_handle_incident_command_with_add_summary(open_updates_dialog_mock):

    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["add_summary"], client, body, respond, ack)
    open_updates_dialog_mock.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.display_current_updates")
def test_handle_incident_command_with_summary(display_current_updates_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["summary"], client, body, respond, ack)
    display_current_updates_mock.assert_called_once_with(client, body, respond, ack)


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(
        ["foo"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with(
        "Unknown command: foo. Type `/sre incident help` to see a list of commands."
    )


@patch("modules.incident.incident_helper.slack_channels.get_stale_channels")
def test_stale_incidents(get_stale_channels_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    get_stale_channels_mock.return_value = [
        {"id": "id", "topic": {"value": "topic_value"}}
    ]
    client.views_open.return_value = {"view": {"id": "view_id"}}
    incident_helper.stale_incidents(client, body, ack)
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)
    client.views_update.assert_called_once_with(view_id="view_id", view=ANY)


def test_channel_item():
    assert incident_helper.channel_item(
        {"id": "id", "topic": {"value": "topic_value"}}
    ) == [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "<#id>",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "topic_value",
                }
            ],
        },
        {"type": "divider"},
    ]


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident(
    mock_incident_status, mock_slack_users, mock_db_operations, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident_id"},
    }
    mock_client.conversations_info.return_value = {
        "channel": {"name": "incident-2024-01-12-test", "is_member": True}
    }
    # Mock the response of client.conversations_archive
    mock_client.conversations_archive.return_value = {"ok": True}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
        mock_respond,
    )

    # Assert that ack was called
    mock_ack.assert_called_once()
    mock_client.conversations_join.assert_not_called()
    mock_client.chat_postEphemeral.assert_not_called()
    mock_incident_status.update_status.assert_called_once_with(
        mock_client,
        mock_respond,
        "Closed",
        "C12345",
        "incident-2024-01-12-test",
        "U12345",
        "incident_id",
    )
    # mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test", "Closed")
    mock_client.chat_postMessage.assert_called_once_with(
        channel="C12345",
        text="<@U12345> has archived this channel 👋",
    )

    # Assert that the Slack client's conversations_archive method was called with the correct channel ID
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")


# Test that the channel that the command is ran in,  is not an incident channel.
@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_not_incident_channel(
    mock_incident_status, mock_slack_users, mock_db_operations, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = None
    # Mock the response of the private message to have been posted as expected
    mock_client.chat_postEphemeral.return_value = {"ok": True}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "user_id": "U12345",
            "channel_name": "some-other-channel",
        },
        mock_ack,
        mock_respond,
    )

    # Assert that ack was called
    mock_ack.assert_called_once()

    # Assert that the private message was posted as expected with the expected text
    expected_text = "Channel some-other-channel is not an incident channel. Please use this command in an incident channel."
    mock_client.chat_postEphemeral.assert_called_once_with(
        channel="C12345", user="U12345", text=expected_text
    )

    mock_incident_status.update_status.assert_not_called()


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_when_client_not_in_channel(
    mock_incident_status, mock_slack_users, mock_db_operations, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident_id"},
    }
    mock_client.conversations_info.return_value = {
        "channel": {"name": "incident-2024-01-12-test", "is_member": False}
    }
    mock_client.conversations_join.return_value = {"ok": True}
    mock_client.conversations_archive.return_value = {"ok": True}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
        mock_respond,
    )

    # Assert that ack was called
    mock_ack.assert_called_once()
    mock_client.conversations_join.assert_called_once_with(channel="C12345")
    mock_incident_status.update_status.assert_called_once_with(
        mock_client,
        mock_respond,
        "Closed",
        "C12345",
        "incident-2024-01-12-test",
        "U12345",
        "incident_id",
    )


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
def test_close_incident_when_client_not_in_channel_throws_error(
    mock_slack_users,
    _mock_db_operations,
    mock_logger,
):
    # the client is not in the channel so it needs to be added
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    # Mock the response of the private message to have been posted as expected
    mock_client.conversations_info.return_value = {
        "ok": True,
        "channel": {"id": "C12345", "name": "incident-channel", "is_member": False},
    }
    mock_client.conversations_join.return_value = {"ok": False, "error": "is_archived"}

    exception_message = "is_archived"
    mock_client.conversations_join.side_effect = Exception(exception_message)

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "user_id": "U12345",
            "channel_name": "incident-channel",
        },
        mock_ack,
        mock_respond,
    )

    mock_logger.exception.assert_called_once_with(
        "client_conversations_error", channel_id="C12345", error="is_archived"
    )


# Test that the channel that the command is ran in,  is not an incident channel.
@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_cant_send_private_message(
    mock_incident_status,
    mock_slack_users,
    _mock_db_operations,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    # Mock the response of the private message to have been posted as expected
    mock_client.chat_postEphemeral.return_value = {
        "ok": False,
        "error": "not_in_channel",
    }

    # mock the excpetion and exception message
    exception_message = "not_in_channel"
    mock_client.chat_postEphemeral.side_effect = Exception(exception_message)

    # The test channel and user IDs
    channel_id = "C12345"
    user_id = "U12345"
    channel_name = "general"  # Not an incident channel

    # Prepare the request body
    body = {"channel_id": channel_id, "user_id": user_id, "channel_name": channel_name}

    # Call the function being tested
    incident_helper.close_incident(mock_client, body, mock_ack, mock_respond)
    mock_client.chat_postEphemeral.assert_called_once_with(
        text="Channel general is not an incident channel. Please use this command in an incident channel.",
        channel="C12345",
        user="U12345",
    )

    mock_logger.exception.assert_called_once_with(
        "client_post_ephemeral_error",
        channel_id=channel_id,
        user_id=user_id,
        error=exception_message,
    )

    mock_incident_status.update_status.assert_not_called()


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_conversations_archive_failure(
    mock_incident_status, mock_slack_users, mock_db_operations, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    # Mock the response of client.bookmarks_list with a valid bookmark
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    # Mock the response of client.conversations_archive to indicate failure
    mock_client.conversations_archive.return_value = {
        "ok": False,
        "error": "not_in_channel",
    }
    mock_client.conversations_archive.side_effect = Exception("not_in_channel")

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
        mock_respond,
    )

    # Ensure that the client's conversations_archive method was called
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")
    mock_logger.exception.assert_called_once_with(
        "client_conversations_archive_error",
        channel_id="C12345",
        user_id="U12345",
        error="not_in_channel",
    )
    error_message = "Could not archive the channel incident-2024-01-12-test due to error: not_in_channel"
    mock_respond.assert_called_once_with(error_message)


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_post_message_failure(
    mock_incident_status,
    mock_slack_users,
    mock_db_operations,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident_id"},
    }
    # Mock the response of client.bookmarks_list with a valid bookmark
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    # Mock the response of client.conversations_archive to indicate success
    mock_client.chat_postMessage.return_value = {
        "ok": False,
        "error": "auth_error",
    }
    mock_client.chat_postMessage.side_effect = Exception("auth_error")

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
        mock_respond,
    )

    mock_client.chat_postMessage.assert_called_once_with(
        channel="C12345", text="<@U12345> has archived this channel 👋"
    )
    mock_logger.exception.assert_called_once_with(
        "client_post_message_error",
        channel_id="C12345",
        user_id="U12345",
        error="auth_error",
    )


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.incident_status")
def test_handle_update_status_command(
    mock_incident_status, mock_db_operations, mock_slack_users, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["Closed"]
    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = [
        {"id": {"S": "incident-2024-01-12-test"}}
    ]
    incident_helper.handle_update_status_command(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
            "text": "Closed",
        },
        mock_respond,
        mock_ack,
        args,
    )

    mock_ack.assert_called_once()
    mock_incident_status.update_status.assert_called_once_with(
        mock_client,
        mock_respond,
        "Closed",
        "C12345",
        "incident-2024-01-12-test",
        "U12345",
    )


@patch("modules.incident.incident_helper.logger")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
@patch("modules.incident.incident_helper.db_operations")
def test_handle_update_status_command_invalid_status(
    mock_db_operations, mock_incident_status, mock_slack_users, mock_logger
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["InvalidStatus"]
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident-2024-01-12-test"}
    }
    # Call the function
    incident_helper.handle_update_status_command(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
            "text": "InvalidStatus",
        },
        mock_respond,
        mock_ack,
        args,
    )

    mock_ack.assert_called_once()
    mock_respond.assert_called_once_with(
        "A valid status must be used with this command:\nIn Progress, Open, Ready to be Reviewed, Reviewed, Closed"
    )
    mock_incident_status.update_status.assert_not_called()


@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
@patch("modules.incident.incident_helper.db_operations")
def test_handle_update_status_command_no_incidents_found(
    mock_db_operations, mock_incident_status, mock_slack_users
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["Closed"]
    mock_db_operations.get_incident_by_channel_id.return_value = []
    # Call the function
    incident_helper.handle_update_status_command(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
            "text": "Closed",
        },
        mock_respond,
        mock_ack,
        args,
    )

    mock_ack.assert_called_once()
    mock_respond.assert_called_once_with(
        "No incident found for this channel. Will not update status in DB record."
    )
    mock_incident_status.update_status.assert_not_called()


def test_parse_incident_datetime_string():
    assert (
        incident_helper.parse_incident_datetime_string("2025-01-23 17:02:16.915368")
        == "2025-01-23 17:02"
    )
    assert (
        incident_helper.parse_incident_datetime_string("2025-01-23 17:02") == "Unknown"
    )
    assert incident_helper.parse_incident_datetime_string("") == "Unknown"
    assert incident_helper.parse_incident_datetime_string("asdf") == "Unknown"
    with pytest.raises(TypeError):
        incident_helper.parse_incident_datetime_string(None)


def test_convert_timestamp():
    assert incident_helper.convert_timestamp("1234567890") == "2009-02-13 23:31:30"
    assert (
        incident_helper.convert_timestamp("1234567890.123456") == "2009-02-13 23:31:30"
    )

    assert incident_helper.convert_timestamp("asdf") == "Unknown"


def generate_incident_data(
    created_at="1234567890",
    incident_commander=None,
    operations_lead=None,
    severity=None,
    start_impact_time=None,
    end_impact_time=None,
    detection_time=None,
    retrospective_url=None,
    environment="prod",
):
    id = str(uuid.uuid4())
    incident_data = {
        "id": id,
        "created_at": created_at,
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "name": "name",
        "status": "status",
        "user_id": "user_id",
        "teams": ["team1", "team2"],
        "report_url": "report_url",
        "meet_url": "meet_url",
        "environment": environment,
        "incident_commander": "incident_commander",
    }

    for key, value in [
        ("incident_commander", incident_commander),
        ("operations_lead", operations_lead),
        ("severity", severity),
        ("start_impact_time", start_impact_time),
        ("end_impact_time", end_impact_time),
        ("detection_time", detection_time),
        ("retrospective_url", retrospective_url),
    ]:
        if value:
            incident_data[key] = value

    return incident_data


@patch("modules.incident.incident_helper.db_operations")
def test_open_updates_dialog(mock_db_operations):
    client = MagicMock()
    ack = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
        "trigger_id": "trigger_id",
    }
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident_id"}
    }
    incident_helper.open_updates_dialog(client, body, ack)
    client.views_open.assert_called_once_with(
        trigger_id="trigger_id",
        view=ANY,
    )


@patch("modules.incident.incident_helper.incident_folder.store_update")
def test_handle_updates_submission(mock_store_update):
    client = MagicMock()
    ack = MagicMock()
    respond = MagicMock()
    view = {
        "private_metadata": json.dumps(
            {
                "incident_id": "incident_id",
                "channel_id": "channel_id",
            }
        ),
        "state": {
            "values": {"updates_block": {"updates_input": {"value": "Test update"}}}
        },
    }
    incident_helper.handle_updates_submission(client, ack, respond, view)
    ack.assert_called_once()
    mock_store_update.assert_called_once_with("incident_id", "Test update")
    client.chat_postMessage.assert_called_once_with(
        channel="channel_id", text="Summary has been updated."
    )


@patch("modules.incident.incident_helper.incident_folder.fetch_updates")
def test_display_current_updates(mock_fetch_updates):
    client = MagicMock()
    ack = MagicMock()
    respond = MagicMock()
    body = {"channel_id": "incident_id"}
    mock_fetch_updates.return_value = ["Update 1", "Update 2"]
    incident_helper.display_current_updates(client, body, respond, ack)
    ack.assert_called_once()
    mock_fetch_updates.assert_called_once_with("incident_id")
    client.chat_postMessage.assert_called_once_with(
        channel="incident_id", text="Current updates:\nUpdate 1\nUpdate 2"
    )

    # Test case when no updates are found
    mock_fetch_updates.return_value = []
    incident_helper.display_current_updates(client, body, respond, ack)
    respond.assert_called_once_with("No updates found for this incident.")
