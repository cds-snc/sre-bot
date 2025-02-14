import json
import os
import uuid
import logging
from unittest.mock import ANY, MagicMock, patch
import pytest

from modules import incident_helper
from models.incidents import Incident

SLACK_SECURITY_USER_GROUP_ID = os.getenv("SLACK_SECURITY_USER_GROUP_ID")


@patch("modules.incident.incident_helper.incident_conversation")
@patch("modules.incident.incident_helper.open_incident_info_view")
def test_handle_incident_command_with_empty_args(
    mock_open_incident_info_view, mock_incident_conversation
):
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "channel_id": "channel_id",
    }
    mock_incident_conversation.is_incident_channel.return_value = (True, False)
    incident_helper.handle_incident_command([], client, body, respond, ack, logger)
    mock_open_incident_info_view.assert_called_once_with(client, body, ack, respond)


@patch("modules.incident.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command(create_folder_mock):
    create_folder_mock.return_value = {"id": "test_id", "name": "foo bar"}
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack, logger
    )
    respond.assert_called_once_with("Folder `foo bar` created.")


@patch("modules.incident.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command_error(create_folder_mock):
    create_folder_mock.return_value = None
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack, logger
    )
    respond.assert_called_once_with("Failed to create folder `foo bar`.")


def test_handle_incident_command_with_help():
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["help"], MagicMock(), MagicMock(), respond, ack, logger
    )
    respond.assert_called_once_with(incident_helper.help_text)


@patch("modules.incident.incident_helper.incident_folder.list_folders_view")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["list-folders"], client, body, respond, ack, logger
    )
    list_folders_mock.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.incident_roles.manage_roles")
def test_handle_incident_command_with_roles(manage_roles_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["roles"], client, body, respond, ack, logger
    )
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
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["close"], client, body, respond, ack, logger
    )
    close_incident_mock.assert_called_once_with(client, logger, body, ack, respond)


@patch("modules.incident.incident_helper.stale_incidents")
def test_handle_incident_command_with_stale(stale_incidents_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["stale"], client, body, respond, ack, logger
    )
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
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["schedule"], client, body, respond, ack, logger
    )
    schedule_retro_mock.schedule_incident_retro.assert_called_once_with(
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
    logger = MagicMock()

    args = ["status", "Ready", "to", "be", "Reviewed"]
    incident_helper.handle_incident_command(args, client, body, respond, ack, logger)
    args.pop(0)
    mock_handle_update_status_command.assert_called_once_with(
        client, logger, body, respond, ack, args
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
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["add_summary"], client, body, respond, ack, logger
    )
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
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["summary"], client, body, respond, ack, logger
    )
    display_current_updates_mock.assert_called_once_with(client, body, respond, ack)


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    incident_helper.handle_incident_command(
        ["foo"], MagicMock(), MagicMock(), respond, ack, logger
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


@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident(mock_incident_status, mock_slack_users, mock_db_operations):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()
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
        mock_logger,
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
        mock_logger,
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
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_not_incident_channel(
    mock_incident_status, mock_slack_users, mock_db_operations
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = None
    # Mock the response of the private message to have been posted as expected
    mock_client.chat_postEphemeral.return_value = {"ok": True}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        mock_logger,
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


@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_when_client_not_in_channel(
    mock_incident_status, mock_slack_users, mock_db_operations
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

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
        mock_logger,
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
        mock_logger,
        "Closed",
        "C12345",
        "incident-2024-01-12-test",
        "U12345",
        "incident_id",
    )


@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
def test_close_incident_when_client_not_in_channel_throws_error(
    mock_slack_users,
    mock_db_operations,
    caplog,
):
    # the client is not in the channel so it needs to be added
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

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
    with caplog.at_level(logging.ERROR):
        incident_helper.close_incident(
            mock_client,
            mock_logger,
            {
                "channel_id": "C12345",
                "user_id": "U12345",
                "channel_name": "incident-channel",
            },
            mock_ack,
            mock_respond,
        )

        assert caplog.records

        # Find the specific log message we're interested in
        log_messages = [record.message for record in caplog.records]

        expected_message = "Failed to join the channel C12345: is_archived"
        assert (
            expected_message in log_messages
        ), "Expected error message not found in log records"


# Test that the channel that the command is ran in,  is not an incident channel.
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_cant_send_private_message(
    mock_incident_status, mock_slack_users, mock_db_operations, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

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

    # Use the caplog fixture to capture logging
    with caplog.at_level(logging.ERROR):
        # Call the function being tested
        incident_helper.close_incident(
            mock_client, mock_logger, body, mock_ack, mock_respond
        )
        mock_client.chat_postEphemeral.assert_called_once_with(
            text="Channel general is not an incident channel. Please use this command in an incident channel.",
            channel="C12345",
            user="U12345",
        )
        # Check that the expected error message was logged
        assert caplog.records  # Ensure there is at least one log record

        # Find the specific log message we're interested in
        log_messages = [record.message for record in caplog.records]

        expected_message = (
            f"Could not post ephemeral message to user {user_id} due to not_in_channel."
        )
        assert (
            expected_message in log_messages
        ), "Expected error message not found in log records"

    mock_incident_status.update_status.assert_not_called()


@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_conversations_archive_failure(
    mock_incident_status, mock_slack_users, mock_db_operations, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

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

    with caplog.at_level(logging.ERROR, logger="commands.helpers.incident_helper"):
        # Call close_incident
        incident_helper.close_incident(
            mock_client,
            mock_logger,
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
    error_message = "Could not archive the channel incident-2024-01-12-test due to error: not_in_channel"
    assert error_message in caplog.text
    mock_respond.assert_called_once_with(error_message)


@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_post_message_failure(
    mock_incident_status, mock_slack_users, mock_db_operations, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

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

    with caplog.at_level(logging.ERROR, logger="commands.helpers.incident_helper"):
        # Call close_incident
        incident_helper.close_incident(
            mock_client,
            mock_logger,
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
    error_message = "Could not post message to channel incident-2024-01-12-test due to error: auth_error"
    assert error_message in caplog.text


@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.db_operations")
@patch("modules.incident.incident_helper.incident_status")
def test_handle_update_status_command(
    mock_incident_status, mock_db_operations, mock_slack_users
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

    args = ["Closed"]
    mock_slack_users.get_user_id_from_request.return_value = "U12345"
    mock_db_operations.get_incident_by_channel_id.return_value = [
        {"id": {"S": "incident-2024-01-12-test"}}
    ]
    incident_helper.handle_update_status_command(
        mock_client,
        mock_logger,
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
        mock_logger,
        "Closed",
        "C12345",
        "incident-2024-01-12-test",
        "U12345",
    )


@patch("modules.incident.incident_helper.slack_users")
@patch("modules.incident.incident_helper.incident_status")
@patch("modules.incident.incident_helper.db_operations")
def test_handle_update_status_command_invalid_status(
    mock_db_operations, mock_incident_status, mock_slack_users
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    mock_logger = MagicMock()

    args = ["InvalidStatus"]
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident-2024-01-12-test"}
    }
    # Call the function
    incident_helper.handle_update_status_command(
        mock_client,
        mock_logger,
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
    mock_logger = MagicMock()

    args = ["Closed"]
    mock_db_operations.get_incident_by_channel_id.return_value = []
    # Call the function
    incident_helper.handle_update_status_command(
        mock_client,
        mock_logger,
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


@patch("modules.incident.incident_helper.incident_information_view")
@patch("modules.incident.incident_helper.db_operations")
def test_open_incident_info_view(mock_db_operations, mock_incident_information_view):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345"},
    }
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident-2024-01-12-test"},
        "channel_id": {"S": "C1234567890"},
        "channel_name": {"S": "incident-2024-01-12-test"},
        "name": {"S": "Test Incident"},
        "user_id": {"S": "U12345"},
        "teams": {"L": [{"S": "team1"}, {"S": "team2"}]},
        "report_url": {"S": "http://example.com/report"},
        "status": {"S": "Open"},
        "meet_url": {"S": "http://example.com/meet"},
        "created_at": {"S": "1234567890"},
        "incident_commander": {"S": "Commander"},
        "operations_lead": {"S": "Lead"},
        "severity": {"S": "High"},
        "start_impact_time": {"S": "1234567890"},
        "end_impact_time": {"S": "1234567890"},
        "detection_time": {"S": "1234567890"},
        "retrospective_url": {"S": "http://example.com/retrospective"},
        "environment": {"S": "prod"},
        "logs": {"L": []},
        "incident_updates": {"L": []},
    }

    incident_data = {
        "id": "incident-2024-01-12-test",
        "channel_id": "C1234567890",
        "channel_name": "incident-2024-01-12-test",
        "name": "Test Incident",
        "user_id": "U12345",
        "teams": ["team1", "team2"],
        "report_url": "http://example.com/report",
        "status": "Open",
        "meet_url": "http://example.com/meet",
        "created_at": "1234567890",
        "incident_commander": "Commander",
        "operations_lead": "Lead",
        "severity": "High",
        "start_impact_time": "1234567890",
        "end_impact_time": "1234567890",
        "detection_time": "1234567890",
        "retrospective_url": "http://example.com/retrospective",
        "environment": "prod",
        "logs": [],
        "incident_updates": [],
    }

    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}
    incident_helper.open_incident_info_view(mock_client, body, mock_ack, mock_respond)
    mock_client.views_open.assert_called_once_with(
        trigger_id="T12345",
        view={"view": [{"block": "block_id"}]},
    )
    mock_incident_information_view.assert_called_once_with(Incident(**incident_data))


@patch("modules.incident.incident_helper.db_operations")
def test_open_incident_view_no_incident_found(mock_db_operations):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345"},
    }
    mock_db_operations.get_incident_by_channel_id.return_value = []
    incident_helper.open_incident_info_view(mock_client, body, mock_ack, mock_respond)
    mock_respond.assert_called_once_with(
        "This is command is only available in incident channels. No incident records found for this channel."
    )


@patch("modules.incident.incident_helper.logging")
@patch("modules.incident.incident_helper.update_field_view")
def test_open_update_field_view(mock_update_field_view, mock_logging):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    private_metadata = json.dumps({"status": "data"})
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345", "private_metadata": private_metadata},
        "actions": [
            {"action_id": "update_incident_field", "value": "action_to_perform"}
        ],
    }
    mock_update_field_view.return_value = {"view": [{"block": "block_id"}]}
    incident_helper.open_update_field_view(mock_client, body, mock_ack, mock_respond)
    mock_update_field_view.assert_called_once_with(
        "action_to_perform", {"status": "data"}
    )
    mock_client.views_push.assert_called_once_with(
        trigger_id="T12345",
        view_id="V12345",
        view={"view": [{"block": "block_id"}]},
    )


@patch("modules.incident.incident_helper.convert_timestamp")
@patch("modules.incident.incident_helper.logging")
def test_incident_information_view(mock_logging, mock_convert_timestamp):
    incident_data = generate_incident_data(
        start_impact_time="1234567890",
        end_impact_time="1234567890",
        detection_time="1234567890",
    )
    id = incident_data["id"]
    mock_convert_timestamp.side_effect = [
        "2009-02-13 23:31:30",
        "Unknown",
        "Unknown",
        "Unknown",
    ]
    incident = Incident(**incident_data)
    private_metadata = json.dumps(incident.model_dump())
    view = incident_helper.incident_information_view(incident)
    assert view == {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {
            "type": "plain_text",
            "text": "Incident Information",
            "emoji": True,
        },
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": private_metadata,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "name",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ID*: " + id,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*:\nstatus",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "status",
                    "action_id": "update_incident_field",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Time Created*:\n2009-02-13 23:31:30",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Detection Time*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "detection_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Start of Impact*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "start_impact_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*End of Impact*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "end_impact_time",
                    "action_id": "update_incident_field",
                },
            },
        ],
    }


@patch("modules.incident.incident_helper.logging")
def test_update_field_view(mock_logging):
    view = incident_helper.update_field_view("status", {"status": "data"})
    mock_logging.info.assert_called_once_with(
        "Loading Update Field View for action: %s", "status"
    )
    assert view == {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "status",
                    "emoji": True,
                },
            }
        ],
    }


@patch("modules.incident.incident_helper.logging")
def test_update_field_view_date_field(mock_logging):
    incident_data = {"status": "data", "detection_time": "1234567890"}
    view = incident_helper.update_field_view("detection_time", incident_data)
    mock_logging.info.assert_called_once_with(
        "Loading Update Field View for action: %s", "detection_time"
    )
    assert view == {
        "type": "modal",
        "callback_id": "update_field_modal",
        "title": {
            "type": "plain_text",
            "text": "Incident Information",
            "emoji": True,
        },
        "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": json.dumps(
            {"action": "detection_time", "incident_data": incident_data}
        ),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "detection_time",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "date_input",
                "element": {
                    "type": "datepicker",
                    "initial_date": "2009-02-13",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a date",
                    },
                    "action_id": "date_picker",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select a date",
                },
            },
            {
                "type": "input",
                "block_id": "time_input",
                "element": {
                    "type": "timepicker",
                    "initial_time": "23:31",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select time",
                        "emoji": True,
                    },
                    "action_id": "time_picker",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select time",
                    "emoji": True,
                },
            },
        ],
    }


@patch("modules.incident.incident_helper.incident_information_view")
@patch("modules.incident.incident_helper.db_operations")
def test_handle_update_field_submission(
    mock_db_operations, mock_incident_information_view
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_logger = MagicMock()
    # update value as a string based on date and time input 2024-01-12 12:00
    updated_value = "1705060800.0"
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "date_input": {"date_picker": {"selected_date": "2024-01-12"}},
                "time_input": {"time_picker": {"selected_time": "12:00"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "detection_time",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}

    incident_helper.handle_update_field_submission(
        mock_client, body, mock_ack, view, mock_logger
    )
    mock_db_operations.update_incident_field.assert_called_once_with(
        mock_logger,
        incident_data["id"],
        "detection_time",
        updated_value,
        incident_data["user_id"],
        type="S",
    )
    mock_client.chat_postMessage.assert_called_once_with(
        channel=incident_data["channel_id"],
        text="<@user_id> has updated the field detection_time to 2024-01-12 12:00",
    )


@patch("modules.incident.incident_helper.incident_information_view")
@patch("modules.incident.incident_helper.db_operations")
def test_handle_update_field_submission_not_supported(
    mock_db_operations, mock_incident_information_view
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_logger = MagicMock()
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "date_input": {"date_picker": {"selected_date": "2024-01-12"}},
                "time_input": {"time_picker": {"selected_time": "12:00"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "unsupported_field",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}

    incident_helper.handle_update_field_submission(
        mock_client, body, mock_ack, view, mock_logger
    )
    mock_db_operations.update_incident_field.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()
    mock_incident_information_view.assert_not_called()
    mock_client.views_update.assert_not_called()
    mock_logger.error.assert_called_once_with("Unknown action: %s", "unsupported_field")


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
