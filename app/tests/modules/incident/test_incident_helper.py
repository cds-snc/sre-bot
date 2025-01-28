import json
import os
import uuid

import pytest
from modules import incident_helper
import logging

from unittest.mock import ANY, MagicMock, call, patch

SLACK_SECURITY_USER_GROUP_ID = os.getenv("SLACK_SECURITY_USER_GROUP_ID")


@patch("modules.incident.incident_helper.open_incident_info_view")
def test_handle_incident_command_with_empty_args(mock_open_incident_info_view):
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    body = {
        "channel_id": "channel_id",
    }
    incident_helper.handle_incident_command([], client, body, respond, ack)
    mock_open_incident_info_view.assert_called_once_with(client, body, ack, respond)


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
    args = ["status", "Ready", "to", "be", "Reviewed"]
    incident_helper.handle_incident_command(args, client, body, respond, ack)
    args.pop(0)
    mock_handle_update_status_command.assert_called_once_with(
        client, body, respond, ack, args
    )


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["foo"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with(
        "Unknown command: foo. Type `/sre incident help` to see a list of commands."
    )


@patch("modules.incident.incident_helper.log_to_sentinel")
def test_archive_channel_action_ignore(mock_log_to_sentinel):
    client = MagicMock()
    body = {
        "actions": [{"value": "ignore"}],
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "message_ts": "message_ts",
        "user": {"id": "user_id"},
    }
    ack = MagicMock()
    respond = MagicMock()
    incident_helper.archive_channel_action(client, body, ack, respond)
    ack.assert_called_once()
    client.chat_update.assert_called_once_with(
        channel="channel_id",
        text="<@user_id> has delayed scheduling and archiving this channel for 14 days.",
        ts="message_ts",
        attachments=[],
    )
    mock_log_to_sentinel.assert_called_once_with(
        "incident_channel_archive_delayed", body
    )


@patch("modules.incident.incident_helper.close_incident")
@patch("modules.incident.incident_helper.log_to_sentinel")
def test_archive_channel_action_archive(
    mock_log_to_sentinel,
    mock_close_incident,
):
    client = MagicMock()
    body = {
        "actions": [{"value": "archive"}],
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "message_ts": "message_ts",
        "user": {"id": "user_id"},
    }
    channel_info = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    ack = MagicMock()
    respond = MagicMock()
    incident_helper.archive_channel_action(client, body, ack, respond)
    assert ack.call_count == 1
    mock_log_to_sentinel.assert_called_once_with("incident_channel_archived", body)
    mock_close_incident.assert_called_once_with(client, channel_info, ack, respond)


@patch("modules.incident.incident_helper.schedule_retro")
@patch("modules.incident.incident_helper.log_to_sentinel")
def test_archive_channel_action_schedule_incident(mock_log_to_sentinel, mock_schedule):
    client = MagicMock()
    body = {
        "actions": [{"value": "schedule_retro"}],
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "message_ts": "message_ts",
        "user": {"id": "user_id"},
        "trigger_id": "trigger_id",
    }
    channel_info = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
        "trigger_id": "trigger_id",
    }
    ack = MagicMock()
    incident_helper.archive_channel_action(client, body, ack, MagicMock())
    assert ack.call_count == 1
    mock_schedule.schedule_incident_retro.assert_called_once_with(
        client, channel_info, ack
    )
    mock_log_to_sentinel.assert_called_once_with("incident_retro_scheduled", body)


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


@patch("modules.incident.incident_helper.incident_status")
def test_close_incident(mock_incident_status):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

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
    )
    # mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test", "Closed")
    mock_client.chat_postMessage.assert_called_once_with(
        channel="C12345",
        text="<@U12345> has archived this channel 👋",
    )

    # Assert that the Slack client's conversations_archive method was called with the correct channel ID
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")


# Test that the channel that the command is ran in,  is not an incident channel.
def test_close_incident_not_incident_channel():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    # Mock the response of the private message to have been posted as expected
    mock_client.chat_postEphemeral.return_value = {"ok": True}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "user_id": "12345",
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
        channel="C12345", user="12345", text=expected_text
    )


@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_when_client_not_in_channel(mock_incident_status):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

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
    )


def test_close_incident_when_client_not_in_channel_throws_error(
    caplog,
):
    # the client is not in the channel so it needs to be added
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
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
            {
                "channel_id": "C12345",
                "user_id": "12345",
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
@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_cant_send_private_message(mock_incident_status, caplog):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

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
            client=mock_client, body=body, ack=mock_ack, respond=mock_respond
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


@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_conversations_archive_failure(
    mock_incident_status, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

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


@patch("modules.incident.incident_helper.incident_status")
def test_close_incident_handles_post_message_failure(mock_incident_status, caplog):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

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


@patch("modules.incident.incident_helper.incident_folder")
@patch("modules.incident.incident_helper.incident_status")
def test_handle_update_status_command(mock_incident_status, mock_incident_folder):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["Closed"]
    mock_incident_folder.lookup_incident.return_value = [
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


@patch("modules.incident.incident_helper.incident_folder")
def test_handle_update_status_command_invalid_status(mock_incident_folder):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["InvalidStatus"]
    mock_incident_folder.lookup_incident.return_value = [
        {"id": {"S": "incident-2024-01-12-test"}}
    ]
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


@patch("modules.incident.incident_helper.incident_folder")
def test_handle_update_status_command_no_incidents_found(mock_incident_folder):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["Closed"]
    mock_incident_folder.lookup_incident.return_value = []
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


@patch("modules.incident.incident_helper.incident_folder")
def test_handle_update_status_command_too_many_incidents(mock_incident_folder):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()

    args = ["Closed"]
    mock_incident_folder.lookup_incident.return_value = [
        {"id": {"S": "incident-2024-01-12-test"}}
    ] * 2
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
        "More than one incident found for this channel. Will not update status in DB record."
    )


@patch("modules.incident.incident_helper.incident_information_view")
@patch("modules.incident.incident_helper.incident_folder")
def test_open_incident_info_view(mock_incident_folder, mock_incident_information_view):
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
    mock_incident_folder.lookup_incident.return_value = [
        {
            "id": {"S": "incident-2024-01-12-test"},
            "channel_id": {"S": "C1234567890"},
        }
    ]
    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}
    incident_helper.open_incident_info_view(mock_client, body, mock_ack, mock_respond)
    mock_client.views_open.assert_called_once_with(
        trigger_id="T12345",
        view={"view": [{"block": "block_id"}]},
    )


@patch("modules.incident.incident_helper.incident_folder")
def test_open_incident_view_no_incident_found(mock_incident_folder):
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
    mock_incident_folder.lookup_incident.return_value = []
    incident_helper.open_incident_info_view(mock_client, body, mock_ack, mock_respond)
    mock_respond.assert_called_once_with(
        "This is command is only available in incident channels. No incident records found for this channel."
    )


@patch("modules.incident.incident_helper.incident_folder")
def test_open_incident_view_multiple_incidents_found(mock_incident_folder):
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
    mock_incident_folder.lookup_incident.return_value = [
        {"id": {"S": "incident-2024-01-12-test"}}
    ] * 2
    incident_helper.open_incident_info_view(mock_client, body, mock_ack, mock_respond)

    mock_respond.assert_called_once_with(
        "More than one incident found for this channel."
    )


@patch("modules.incident.incident_helper.logging")
@patch("modules.incident.incident_helper.update_field_view")
def test_open_update_field_view(mock_update_field_view, mock_logging):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_respond = MagicMock()
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345"},
        "actions": [{"action_id": "action_to_perform"}],
    }
    mock_update_field_view.return_value = {"view": [{"block": "block_id"}]}
    incident_helper.open_update_field_view(mock_client, body, mock_ack, mock_respond)
    mock_update_field_view.assert_called_once_with("action_to_perform")
    mock_client.views_push.assert_called_once_with(
        trigger_id="T12345",
        view_id="V12345",
        view={"view": [{"block": "block_id"}]},
    )


@patch("modules.incident.incident_helper.parse_incident_datetime_string")
@patch("modules.incident.incident_helper.logging")
def test_incident_information_view(mock_logging, mock_parse_incident_datetime_string):
    incident_data = generate_incident_data()
    id = incident_data["id"]["S"]
    mock_parse_incident_datetime_string.side_effect = [
        "2025-01-23 17:02",
        "Unknown",
        "Unknown",
        "Unknown",
    ]
    view = incident_helper.incident_information_view(incident_data)
    mock_logging.info.assert_called_once_with(
        f"Loading Status View for:\n{incident_data}"
    )
    mock_parse_incident_datetime_string.assert_has_calls(
        [
            call("2025-01-23 17:02:16.915368"),
            call("Unknown"),
            call("Unknown"),
            call("Unknown"),
        ]
    )
    assert view == {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {
            "type": "plain_text",
            "text": "Incident Information",
            "emoji": True,
        },
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "channel_name",
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
                    "value": "click_me_123",
                    "action_id": "update_status",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Time Created*:\n2025-01-23 17:02",
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
                    "value": "click_me_123",
                    "action_id": "update_detection_time",
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
                    "value": "click_me_123",
                    "action_id": "update_start_impact_time",
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
                    "value": "click_me_123",
                    "action_id": "update_end_impact_time",
                },
            },
        ],
    }


@patch("modules.incident.incident_helper.logging")
def test_update_field_view(mock_logging):
    view = incident_helper.update_field_view("update_status")
    mock_logging.info.assert_called_once_with(
        "Loading Update Field View for update_status"
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
                    "text": "update_status",
                    "emoji": True,
                },
            }
        ],
    }


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


def generate_incident_data(
    created_at="2025-01-23 17:02:16.915368",
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
        "id": {"S": id},
        "created_at": {"S": created_at},
        "channel_id": {"S": "channel_id"},
        "channel_name": {"S": "channel_name"},
        "status": {"S": "status"},
        "user_id": {"S": "user_id"},
        "teams": {"SS": ["team1", "team2"]},
        "report_url": {"S": "report_url"},
        "meet_url": {"S": "meet_url"},
        "environment": {"S": environment},
        "incident_commander": {"S": "incident_commander"},
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
            incident_data[key] = {"S": value}

    return incident_data
