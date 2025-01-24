import json
import os
from modules import incident_helper
import logging

from unittest.mock import ANY, MagicMock, patch

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


@patch("modules.incident.incident_helper.schedule_incident_retro")
def test_handle_incident_command_with_retro(schedule_incident_retro_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(["schedule"], client, body, respond, ack)
    schedule_incident_retro_mock.assert_called_once_with(client, body, ack)


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


@patch("modules.incident.incident_helper.schedule_incident_retro")
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
    mock_schedule.assert_called_once_with(client, channel_info, ack)
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


@patch("modules.incident.incident_helper.logging")
def test_confirm_click(mock_logging):
    ack = MagicMock()
    body = {
        "user": {"id": "user_id", "username": "username"},
    }
    incident_helper.confirm_click(ack, body, client=MagicMock())
    ack.assert_called_once()
    mock_logging.info.assert_called_once_with(
        "User username viewed the calendar event."
    )


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


@patch("modules.incident.incident_helper.logging.error")
def test_schedule_incident_retro_not_incident_channel_exception(mock_logging_error):
    mock_ack = MagicMock()
    mock_client = MagicMock()

    # Mock the response of the private message to have been posted as expected
    mock_client.chat_postEphemeral.return_value = {
        "ok": False,
        "error": "not_in_channel",
    }

    # Mock the exception and exception message
    exception_message = "not_in_channel"
    mock_client.chat_postEphemeral.side_effect = Exception(exception_message)

    # The test channel and user IDs
    channel_id = "C12345"
    user_id = "U12345"
    channel_name = "general"  # Not an incident channel

    # Prepare the request body
    body = {"channel_id": channel_id, "user_id": user_id, "channel_name": channel_name}

    # Call the function being tested
    incident_helper.schedule_incident_retro(client=mock_client, body=body, ack=mock_ack)

    # Ensure the ack method was called
    mock_ack.assert_called_once()

    # Ensure the correct error message was posted to the channel
    expected_text = "Channel general is not an incident channel. Please use this command in an incident channel."
    mock_client.chat_postEphemeral.assert_called_once_with(
        text=expected_text,
        channel=channel_id,
        user=user_id,
    )

    # Check that the expected error message was logged
    expected_log_message = f"Could not post ephemeral message to user {user_id} due to {exception_message}."
    mock_logging_error.assert_called_once_with(expected_log_message)


@patch("modules.incident.incident_helper.logging")
def test_schedule_incident_retro_no_bookmarks(mock_logging):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.bookmarks_list.return_value = {"ok": False, "error": "not_in_channel"}

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()
    mock_logging.warning.assert_called_once_with(
        "No bookmark link for the incident document found for channel %s",
        "incident-2024-01-12-test",
    )


def test_schedule_incident_retro_successful_no_bots():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U34333"]}
    mock_client.conversations_members.return_value = {"members": ["U12345", "U67890"]}
    mock_client.conversations_info.return_value = {
        "channel": {
            "topic": {"value": "Retro Topic"},
            "purpose": {"value": "Retro Purpose"},
        }
    }
    mock_client.users_info.side_effect = [
        {"user": {"id": "U12345", "real_name": "User1", "email": "user1@example.com"}},
        {"user": {"id": "U6789", "real_name": "User2", "email": "user2@example.com"}},
        {
            "user": {
                "id": "U12345",
                "real_name": "BotUser",
                "email": "user3@example.com",
                "bot_id": "B12345",
            }
        },  # this simulates a bot user
    ]

    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.conversations_members.assert_called_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 2
    )  # Ensure we tried to fetch info for two users, one being a bot

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_successful_bots():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U3333"]}
    mock_client.conversations_members.return_value = {
        "members": ["U12345", "U67890", "U54321"]
    }
    mock_client.conversations_info.return_value = {
        "channel": {
            "topic": {"value": "Retro Topic"},
            "purpose": {"value": "Retro Purpose"},
        }
    }

    mock_client.users_info.side_effect = [
        {"user": {"id": "U12345", "real_name": "User1", "email": "user1@example.com"}},
        {"user": {"id": "U6789", "real_name": "User2", "email": "user2@example.com"}},
        {
            "user": {
                "id": "U12345",
                "real_name": "BotUser",
                "email": "user3@example.com",
                "bot_id": "B12345",
            }
        },  # this simulates a bot user
    ]

    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.conversations_members.assert_called_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 3
    )  # Ensure we tried to fetch info for three users, one being a bot

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_successful_no_security_group():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": []}
    mock_client.conversations_members.return_value = {
        "members": ["U12345", "U67890", "U54321"]
    }
    mock_client.conversations_info.return_value = {
        "channel": {
            "topic": {"value": "Retro Topic"},
            "purpose": {"value": "Retro Purpose"},
        }
    }
    mock_client.users_info.side_effect = [
        {"user": {"id": "U12345", "real_name": "User1", "email": "user1@example.com"}},
        {"user": {"id": "U6789", "real_name": "User2", "email": "user2@example.com"}},
        {
            "user": {
                "id": "U12345",
                "real_name": "BotUser",
                "email": "user3@example.com",
                "bot_id": "B12345",
            }
        },  # this simulates a bot user
    ]
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
    }

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.conversations_members.assert_called_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 3
    )  # Ensure we tried to fetch info for two users, minus the user being in the security group

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {
            "name": "incident-2024-01-12-test",
            "incident_document": "dummy_document_id",
            "channel_id": "C1234567890",
        }
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_with_no_users():
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

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

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


def test_schedule_incident_retro_with_no_topic():
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

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

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


def test_schedule_incident_retro_with_no_name():
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

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

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


def test_schedule_incident_retro_with_no_purpose():
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

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

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
    incident_helper.save_incident_retro(
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
    incident_helper.save_incident_retro(
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
    incident_helper.save_incident_retro(
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


@patch("modules.incident.incident_helper.incident_status")
@patch("modules.incident.incident_helper.incident_folder")
def test_open_incident_info_view(mock_incident_folder, mock_incident_status):
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
    mock_incident_status.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }
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
@patch("modules.incident.incident_helper.incident_status")
def test_open_update_field_view(mock_incident_status, mock_logging):
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
    mock_incident_status.update_field_view.return_value = {
        "view": [{"block": "block_id"}]
    }
    incident_helper.open_update_field_view(mock_client, body, mock_ack, mock_respond)
    mock_incident_status.update_field_view.assert_called_once_with("action_to_perform")
    mock_client.views_push.assert_called_once_with(
        trigger_id="T12345",
        view_id="V12345",
        view={"view": [{"block": "block_id"}]},
    )
