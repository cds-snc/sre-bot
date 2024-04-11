import json
import os
from modules import incident_helper
import logging


from unittest.mock import ANY, MagicMock, patch

SLACK_SECURITY_USER_GROUP_ID = os.getenv("SLACK_SECURITY_USER_GROUP_ID")


def test_handle_incident_command_with_empty_args():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command([], MagicMock(), MagicMock(), respond, ack)
    respond.assert_called_once_with(incident_helper.help_text)


@patch("modules.incident.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command(create_folder_mock):
    create_folder_mock.return_value = "folder created"
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with("folder created")


def test_handle_incident_command_with_help():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["help"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with(incident_helper.help_text)


@patch("modules.incident.incident_helper.list_folders")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["list-folders"], client, body, respond, ack
    )
    list_folders_mock.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.manage_roles")
def test_handle_incident_command_with_roles(manage_roles_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(["roles"], client, body, respond, ack)
    manage_roles_mock.assert_called_once_with(client, body, ack, respond)


@patch("modules.incident.incident_helper.stale_incidents")
def test_handle_incident_command_with_stale(stale_incidents_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(["stale"], client, body, respond, ack)
    stale_incidents_mock.assert_called_once_with(client, body, ack)


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["foo"], MagicMock(), MagicMock(), respond, ack
    )
    respond.assert_called_once_with(
        "Unknown command: foo. Type `/sre incident help` to see a list of commands."
    )


def test_add_folder_metadata():
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"id": "bar"}}
    ack = MagicMock()
    incident_helper.add_folder_metadata(client, body, ack)
    ack.assert_called_once()
    client.views_update.assert_called_once_with(view_id="bar", view=ANY)


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
    incident_helper.archive_channel_action(client, body, ack)
    ack.assert_called_once()
    client.chat_update(
        channel="channel_id",
        text="<@user_id> has delayed archiving this channel for 14 days.",
        ts="message_ts",
        attachments=[],
    )
    mock_log_to_sentinel.assert_called_once_with(
        "incident_channel_archive_delayed", body
    )


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
@patch("modules.incident.incident_helper.log_to_sentinel")
def test_archive_channel_action_archive(
    mock_log_to_sentinel, mock_extract_id, mock_update_spreadsheet, mock_close_document
):
    client = MagicMock()
    body = {
        "actions": [{"value": "archive"}],
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "message_ts": "message_ts",
        "user": {"id": "user_id"},
    }
    ack = MagicMock()
    incident_helper.archive_channel_action(client, body, ack)
    assert ack.call_count == 2
    mock_log_to_sentinel.assert_called_once_with("incident_channel_archived", body)


@patch("modules.incident.incident_helper.log_to_sentinel")
def test_archive_channel_action_schedule_incident(mock_log_to_sentinel):
    client = MagicMock()
    channel_info = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "user_id": "user_id",
    }
    ack = MagicMock()
    incident_helper.schedule_incident_retro(client, channel_info, ack)
    assert ack.call_count == 1


@patch("modules.incident.incident_helper.google_drive.delete_metadata")
@patch("modules.incident.incident_helper.view_folder_metadata")
def test_delete_folder_metadata(view_folder_metadata_mock, delete_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"private_metadata": "bar"}}
    ack = MagicMock()
    incident_helper.delete_folder_metadata(client, body, ack)
    ack.assert_called_once()
    delete_metadata_mock.assert_called_once_with("bar", "foo")
    view_folder_metadata_mock.assert_called_once_with(
        client,
        {"actions": [{"value": "bar"}], "view": {"private_metadata": "bar"}},
        ack,
    )


@patch("modules.incident.incident_helper.google_drive.list_folders")
@patch("modules.incident.incident_helper.folder_item")
def test_list_folders(folder_item_mock, list_folders_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    list_folders_mock.return_value = [{"id": "foo", "name": "bar"}]
    folder_item_mock.return_value = [["folder item"]]
    incident_helper.list_folders(client, body, ack)
    list_folders_mock.assert_called_once()
    folder_item_mock.assert_called_once_with({"id": "foo", "name": "bar"})
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)


@patch("modules.incident.incident_helper.google_drive.get_document_by_channel_name")
def test_manage_roles(get_document_by_channel_name_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-channel_name",
        "trigger_id": "trigger_id",
    }
    ack = MagicMock()
    respond = MagicMock()
    get_document_by_channel_name_mock.return_value = [
        {"id": "file_id", "appProperties": {"ic_id": "ic_id", "ol_id": "ol_id"}}
    ]
    incident_helper.manage_roles(client, body, ack, respond)
    ack.assert_called_once()
    get_document_by_channel_name_mock.assert_called_once_with("channel_name")
    client.views_open.assert_called_once_with(trigger_id="trigger_id", view=ANY)


@patch("modules.incident.incident_helper.google_drive.get_document_by_channel_name")
def test_manage_roles_with_no_result(get_document_by_channel_name_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-channel_name",
        "trigger_id": "trigger_id",
    }
    ack = MagicMock()
    respond = MagicMock()
    get_document_by_channel_name_mock.return_value = []
    incident_helper.manage_roles(client, body, ack, respond)
    ack.assert_called_once()
    respond.assert_called_once_with(
        "No incident document found for `channel_name`. Please make sure the channel matches the document name."
    )


@patch("modules.incident.incident_helper.google_drive.add_metadata")
def test_save_incident_roles(add_metadata_mock):
    client = MagicMock()
    ack = MagicMock()
    view = {
        "private_metadata": json.dumps(
            {
                "ic_id": "ic_id",
                "ol_id": "ol_id",
                "id": "file_id",
                "channel_id": "channel_id",
            }
        ),
        "state": {
            "values": {
                "ic_name": {"ic_select": {"selected_user": "selected_ic"}},
                "ol_name": {"ol_select": {"selected_user": "selected_ol"}},
            }
        },
    }
    incident_helper.save_incident_roles(client, ack, view)
    ack.assert_called_once()
    add_metadata_mock.assert_any_call("file_id", "ic_id", "selected_ic")
    add_metadata_mock.assert_any_call("file_id", "ol_id", "selected_ol")
    client.chat_postMessage.assert_any_call(
        text="<@selected_ic> has been assigned as incident commander for this incident.",
        channel="channel_id",
    )
    client.chat_postMessage.assert_any_call(
        text="<@selected_ol> has been assigned as operations lead for this incident.",
        channel="channel_id",
    )
    client.conversations_setTopic.assert_called_once_with(
        topic="IC: <@selected_ic> / OL: <@selected_ol>", channel="channel_id"
    )


@patch("modules.incident.incident_helper.google_drive.add_metadata")
@patch("modules.incident.incident_helper.view_folder_metadata")
def test_save_metadata(view_folder_metadata_mock, add_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"private_metadata": "bar"}}
    view = {
        "state": {
            "values": {
                "key": {"key": {"value": "key"}},
                "value": {"value": {"value": "value"}},
            }
        },
        "private_metadata": "bar",
    }
    ack = MagicMock()
    incident_helper.save_metadata(client, body, ack, view)
    ack.assert_called_once()
    add_metadata_mock.assert_called_once_with("bar", "key", "value")
    view_folder_metadata_mock.assert_called_once_with(
        client,
        {"actions": [{"value": "bar"}]},
        ack,
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


@patch("modules.incident.incident_helper.google_drive.list_metadata")
@patch("modules.incident.incident_helper.metadata_items")
def test_view_folder_metadata_open(metadata_items_mock, list_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "trigger_id": "trigger_id"}
    ack = MagicMock()
    list_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_helper.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    list_metadata_mock.assert_called_once_with("foo")
    metadata_items_mock.assert_called_once_with(
        {"name": "folder", "appProperties": [{"key": "key", "value": "value"}]}
    )
    client.views_open(trigger_id="trigger_id", view=ANY)


@patch("modules.incident.incident_helper.google_drive.list_metadata")
@patch("modules.incident.incident_helper.metadata_items")
def test_view_folder_metadata_update(metadata_items_mock, list_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"id": "view_id"}}
    ack = MagicMock()
    list_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_helper.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    list_metadata_mock.assert_called_once_with("foo")
    metadata_items_mock.assert_called_once_with(
        {"name": "folder", "appProperties": [{"key": "key", "value": "value"}]}
    )
    client.views_update(view_id="view_id", view=ANY)


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


def test_folder_item():
    assert incident_helper.folder_item({"id": "foo", "name": "bar"}) == [
        {
            "accessory": {
                "action_id": "view_folder_metadata",
                "text": {
                    "emoji": True,
                    "text": "Manage metadata",
                    "type": "plain_text",
                },
                "type": "button",
                "value": "foo",
            },
            "text": {"text": "*bar*", "type": "mrkdwn"},
            "type": "section",
        },
        {
            "elements": [
                {
                    "text": "<https://drive.google.com/drive/u/0/folders/foo|View in Google Drive>",
                    "type": "mrkdwn",
                }
            ],
            "type": "context",
        },
        {"type": "divider"},
    ]


def test_metadata_items_empty():
    empty = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*No metadata found. Click the button above to add metadata.*",
            },
        },
    ]
    assert incident_helper.metadata_items({}) == empty
    assert incident_helper.metadata_items({"appProperties": []}) == empty


def test_metadata_items():
    assert incident_helper.metadata_items({"appProperties": {"key": "value"}}) == [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*key*\nvalue",
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Delete metadata",
                    "emoji": True,
                },
                "value": "key",
                "style": "danger",
                "action_id": "delete_folder_metadata",
            },
        },
    ]


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
def test_close_incident(mock_extract_id, mock_update_spreadsheet, mock_close_document):
    mock_client = MagicMock()
    mock_ack = MagicMock()

    # Mock the response of client.bookmarks_list
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/dummy_document_id/edit",
            }
        ],
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
    )

    # Assert that ack was called
    mock_ack.assert_called_once()

    # Assert that extract_google_doc_id was called with the correct URL
    mock_extract_id.assert_called_once_with(
        "https://docs.google.com/document/d/dummy_document_id/edit"
    )

    # Assert that the Google Drive document and spreadsheet update methods were called
    mock_close_document.assert_called_once_with("dummy_document_id")
    mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test")

    # Assert that the Slack client's conversations_archive method was called with the correct channel ID
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id", return_value=None
)
def test_close_incident_no_bookmarks(
    mock_extract_id, mock_update_spreadsheet, mock_close_document
):
    mock_client = MagicMock()
    mock_ack = MagicMock()

    # Mock client.bookmarks_list to return no bookmarks
    mock_client.bookmarks_list.return_value = {"ok": True, "bookmarks": []}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
    )

    # Assertions to ensure that document update functions are not called as there are no bookmarks
    mock_extract_id.assert_not_called()
    mock_close_document.assert_not_called()
    mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test")


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id", return_value=None
)
def test_close_incident_no_bookmarks_error(
    mock_extract_id, mock_update_spreadsheet, mock_close_document
):
    mock_client = MagicMock()
    mock_ack = MagicMock()

    # Mock client.bookmarks_list to return no bookmarks
    mock_client.bookmarks_list.return_value = {"ok": False, "error": "not_in_channel"}

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
    )

    # Assertions to ensure that document update functions are not called as there are no bookmarks
    mock_extract_id.assert_not_called()
    mock_close_document.assert_not_called()
    mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test")


# Test that the channel that the command is ran in,  is not an incident channel.
def test_close_incident_not_incident_channel():
    mock_client = MagicMock()
    mock_ack = MagicMock()

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
    )

    # Assert that ack was called
    mock_ack.assert_called_once()

    # Assert that the private message was posted as expected with the expected text
    expected_text = "Channel some-other-channel is not an incident channel. Please use this command in an incident channel."
    mock_client.chat_postEphemeral.assert_called_once_with(
        channel="C12345", user="12345", text=expected_text
    )


# Test that the channel that the command is ran in,  is not an incident channel.
def test_close_incident_cant_send_private_message(caplog):
    mock_client = MagicMock()
    mock_ack = MagicMock()

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
        incident_helper.close_incident(client=mock_client, body=body, ack=mock_ack)

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


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
def test_conversations_archive_fail(
    mock_extract_id, mock_update_spreadsheet, mock_close_document
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
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

    # Call close_incident
    incident_helper.close_incident(
        mock_client,
        {
            "channel_id": "C12345",
            "channel_name": "incident-2024-01-12-test",
            "user_id": "U12345",
        },
        mock_ack,
    )

    # Assertions
    # Ensure that the Google Drive document update method was called even if archiving fails
    mock_close_document.assert_called_once_with("dummy_document_id")
    mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test")

    # Ensure that the client's conversations_archive method was called
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
def test_conversations_archive_fail_error_message(
    mock_extract_id, mock_update_spreadsheet, mock_close_document, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
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
        "ok": True,
        "error": "not_in_channel",
    }

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
        )

    # Assertions
    # Ensure that the Google Drive document update method was called even if archiving fails
    mock_close_document.assert_called_once_with("dummy_document_id")
    mock_update_spreadsheet.assert_called_once_with("#2024-01-12-test")

    # Ensure that the client's conversations_archive method was called
    mock_client.conversations_archive.assert_called_once_with(channel="C12345")

    assert (
        "Could not archive the channel incident-2024-01-12-test - not_in_channel"
        not in caplog.text
    )


@patch("modules.incident.incident_helper.google_drive.close_incident_document")
@patch(
    "modules.incident.incident_helper.google_drive.update_spreadsheet_close_incident"
)
@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
def test_conversations_archive_succeeds_post_message_who_archived(
    mock_extract_id, mock_update_spreadsheet, mock_close_document, caplog
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-channel_name",
        "user_id": "user_id",
    }
    incident_helper.close_incident(mock_client, body, mock_ack)

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
    mock_client.conversations_archive.return_value = {
        "ok": True,
    }

    # assert that the channel was archived
    mock_client.conversations_archive.assert_called_once_with(channel="channel_id")

    # assert message was posted to archived channel.
    mock_client.chat_postMessage.assert_any_call(
        text="<@user_id> has archived this channel 👋",
        channel="channel_id",
    )


def test_return_channel_name_with_prefix():
    # Test the function with a string that includes the prefix.
    assert incident_helper.return_channel_name("incident-abc123") == "#abc123"


def test_return_channel_name_without_prefix():
    # Test the function with a string that does not include the prefix.
    assert incident_helper.return_channel_name("general") == "general"


def test_return_channel_name_empty_string():
    # Test the function with an empty string.
    assert incident_helper.return_channel_name("") == ""


def test_return_channel_name_prefix_only():
    # Test the function with a string that is only the prefix.
    assert incident_helper.return_channel_name("incident-") == "#"


def test_schedule_incident_retro_successful_no_bots():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U34333"]}
    mock_client.conversations_members.return_value = {"members": ["U12345", "U67890"]}
    mock_client.conversations_info.return_value = {
        "channel": {"topic": {"value": "Retro Topic"}}
    }
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user1@example.com"}}},
        {"user": {"profile": {"email": "user2@example.com"}}},
    ]

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.usergroups_users_list.assert_called_once_with(
        usergroup=SLACK_SECURITY_USER_GROUP_ID
    )
    mock_client.conversations_members.assert_called_once_with(channel="C1234567890")
    mock_client.conversations_info.assert_called_once_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 2
    )  # Ensure we tried to fetch info for two users, one being a bot

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {"emails": ["user1@example.com", "user2@example.com"], "topic": "Retro Topic"}
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
        "channel": {"topic": {"value": "Retro Topic"}}
    }
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user1@example.com"}}},
        {"user": {"profile": {"email": "user2@example.com"}}},
        {
            "user": {"profile": {"email": "user3@example.com", "bot_id": "B12345"}}
        },  # This simulates a bot user
    ]

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.usergroups_users_list.assert_called_once_with(
        usergroup=SLACK_SECURITY_USER_GROUP_ID
    )
    mock_client.conversations_members.assert_called_once_with(channel="C1234567890")
    mock_client.conversations_info.assert_called_once_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 3
    )  # Ensure we tried to fetch info for three users, one being a bot

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {"emails": ["user1@example.com", "user2@example.com"], "topic": "Retro Topic"}
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_successful_security_group():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U12345", "U444444"]}
    mock_client.conversations_members.return_value = {
        "members": ["U12345", "U67890", "U54321"]
    }
    mock_client.conversations_info.return_value = {
        "channel": {"topic": {"value": "Retro Topic"}}
    }
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user2@example.com"}}},
        {
            "user": {"profile": {"email": "user3@example.com", "bot_id": "B12345"}}
        },  # This simulates a bot user
    ]

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.usergroups_users_list.assert_called_once_with(
        usergroup=SLACK_SECURITY_USER_GROUP_ID
    )
    mock_client.conversations_members.assert_called_once_with(channel="C1234567890")
    mock_client.conversations_info.assert_called_once_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 2
    )  # Ensure we tried to fetch info for two users, minus the user being in the security group

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {"emails": ["user2@example.com"], "topic": "Retro Topic"}
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
        "channel": {"topic": {"value": "Retro Topic"}}
    }
    mock_client.users_info.side_effect = [
        {"user": {"profile": {"email": "user1@example.com"}}},
        {"user": {"profile": {"email": "user2@example.com"}}},
        {
            "user": {"profile": {"email": "user3@example.com", "bot_id": "B12345"}}
        },  # This simulates a bot user
    ]

    body = {
        "channel_id": "C1234567890",
        "trigger_id": "T1234567890",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
    }

    incident_helper.schedule_incident_retro(mock_client, body, mock_ack)

    mock_ack.assert_called_once()

    # Verify the correct API calls were made
    mock_client.usergroups_users_list.assert_called_once_with(
        usergroup=SLACK_SECURITY_USER_GROUP_ID
    )
    mock_client.conversations_members.assert_called_once_with(channel="C1234567890")
    mock_client.conversations_info.assert_called_once_with(channel="C1234567890")

    # Check the users_info method was called correctly
    calls = [call for call in mock_client.users_info.call_args_list]
    assert (
        len(calls) == 3
    )  # Ensure we tried to fetch info for two users, minus the user being in the security group

    # Verify the modal payload contains the correct data
    expected_data = json.dumps(
        {"emails": ["user1@example.com", "user2@example.com"], "topic": "Retro Topic"}
    )
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_with_no_users():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {
        "channel": {"topic": {"value": "Retro Topic"}}
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

    # construct the expected data object
    expected_data = json.dumps({"emails": [], "topic": "Retro Topic"})
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


def test_schedule_incident_retro_with_no_topic():
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_client.usergroups_users_list.return_value = {"users": ["U444444"]}
    mock_client.conversations_info.return_value = {"channel": {"topic": {"value": ""}}}
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
    expected_data = json.dumps({"emails": [], "topic": "Incident Retro"})
    # Assertions to validate behavior when no users are present in the channel
    assert (
        mock_client.views_open.call_args[1]["view"]["private_metadata"] == expected_data
    )


@patch("integrations.google_workspace.google_calendar.schedule_event")
def test_save_incident_retro_success(schedule_event_mock):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = "http://example.com/event"
    body_mock = {"trigger_id": "some_trigger_id"}
    view_mock_with_link = {"private_metadata": "event details for scheduling"}

    # Call the function
    incident_helper.save_incident_retro(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened

    # Verify the modal content for success
    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Successfully schduled calender event!*"
    )


@patch("integrations.google_workspace.google_calendar.schedule_event")
def test_save_incident_retro_failure(schedule_event_mock):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    schedule_event_mock.return_value = None
    body_mock = {"trigger_id": "some_trigger_id"}
    view_mock_with_link = {"private_metadata": "event details for scheduling"}

    # Call the function
    incident_helper.save_incident_retro(
        mock_client, mock_ack, body_mock, view_mock_with_link
    )

    # Assertions
    mock_ack.assert_called_once()  # Ensure ack() was called
    mock_client.views_open.assert_called_once()  # Ensure the modal was opened

    # Verify the modal content for success
    assert (
        mock_client.views_open.call_args[1]["view"]["blocks"][0]["text"]["text"]
        == "*Could not schedule event - no free time was found!*"
    )
