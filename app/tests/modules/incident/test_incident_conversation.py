from unittest.mock import MagicMock, patch
from modules.incident import incident_conversation
import pytest

from slack_sdk.errors import SlackApiError


def test_is_floppy_disk_true():
    # Test case where the reaction is 'floppy_disk'
    event = {"reaction": "floppy_disk"}
    assert (
        incident_conversation.is_floppy_disk(event) is True
    ), "The function should return True for 'floppy_disk' reaction"


def test_is_floppy_disk_false():
    # Test case where the reaction is not 'floppy_disk'
    event = {"reaction": "thumbs_up"}
    assert (
        incident_conversation.is_floppy_disk(event) is False
    ), "The function should return False for reactions other than 'floppy_disk'"


def test_is_incident_channel_false():
    # Test case where the channel name does not contain 'incident'
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"name": "general", "is_archived": False, "is_member": False},
    }
    client.conversations_join.return_value = {"ok": True}
    assert incident_conversation.is_incident_channel(client, logger, channel_id) == (
        False,
        False,
    )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_not_called()


def test_is_incident_channel_true_archived_not_member():
    # Test case where the channel name contains 'incident'
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"name": "incident-123", "is_archived": True, "is_member": False},
    }

    assert incident_conversation.is_incident_channel(client, logger, channel_id) == (
        True,
        False,
    )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_not_called()


def test_is_incident_channel_true_not_archived_member():
    # Test case where the channel name contains 'incident'
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"name": "incident-123", "is_archived": False, "is_member": True},
    }

    assert incident_conversation.is_incident_channel(client, logger, channel_id) == (
        True,
        False,
    )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_not_called()


def test_is_incident_channel_raises_slack_api_error():
    # Test case where the Slack API call raises an exception
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.side_effect = SlackApiError(
        message="error", response={"ok": False, "error": "error"}
    )

    with pytest.raises(SlackApiError):
        assert incident_conversation.is_incident_channel(
            client, logger, channel_id
        ) == (
            False,
            False,
        )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_not_called()


def test_is_incident_channel_true_not_archived_not_member():
    # Test case where the channel name contains 'incident'
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"name": "incident-123", "is_archived": False, "is_member": False},
    }

    client.conversations_join.return_value = {"ok": True}
    assert incident_conversation.is_incident_channel(client, logger, channel_id) == (
        True,
        False,
    )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_called_once_with(channel=channel_id)


def test_is_incident_dev_channel_true():
    # Test case where the channel name contains 'incident-dev'
    client = MagicMock()
    logger = MagicMock()
    channel_id = "C123456"
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"name": "incident-dev-123"},
    }
    client.conversations_join.return_value = {"ok": True}

    assert incident_conversation.is_incident_channel(client, logger, channel_id) == (
        True,
        True,
    )
    client.conversations_info.assert_called_once_with(channel=channel_id)
    client.conversations_join.assert_called_once_with(channel=channel_id)


def test_multiline_entries_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Message one
    ➡️ [2024-03-05 18:24:30 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-05 18:24:30 ET](https://example.com/link2) Jane Smith: Message two\n\n\n➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Message one"
    assert (
        incident_conversation.rearrange_by_datetime_ascending(input_text).strip()
        == expected_output
    )


def test_rearrange_single_entry():
    input_text = "➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Only one message"
    expected_output = "➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Only one message"
    assert (
        incident_conversation.rearrange_by_datetime_ascending(input_text).strip()
        == expected_output
    )


def test_rearrange_no_entries():
    input_text = ""
    expected_output = ""
    assert (
        incident_conversation.rearrange_by_datetime_ascending(input_text).strip()
        == expected_output
    )


def test_entries_out_of_order_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ [2024-03-07 11:00:00 ET](https://example.com/link1) John Doe: Message one
    ➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two\n\n\n➡️ [2024-03-07 11:00:00 ET](https://example.com/link1) John Doe: Message one"
    assert (
        incident_conversation.rearrange_by_datetime_ascending(input_text).strip()
        == expected_output
    )


def test_invalid_entries_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ Invalid Entry
    ➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two\n"
    assert (
        incident_conversation.rearrange_by_datetime_ascending(input_text)
        == expected_output
    )


def test_empty_input_rearrange_by_datetime_ascending():
    assert incident_conversation.rearrange_by_datetime_ascending("") == ""


def test_no_datetime_entries_rearrange_by_datetime_ascending():
    input_text = "Message without datetime\nAnother message"
    assert incident_conversation.rearrange_by_datetime_ascending(input_text) == ""


def test_convert_epoch_to_datetime_est_known_epoch_time():
    # Example: 0 epoch time corresponds to 1969-12-31 19:00:00 EST
    assert (
        incident_conversation.convert_epoch_to_datetime_est(0)
        == "1969-12-31 19:00:00 ET"
    )


def test_convert_epoch_to_datetime_est_daylight_saving_time_change():
    # Test with an epoch time known to fall in DST transition
    # For example, 1583652000 corresponds to 2020-03-08 03:20:00 EST
    assert (
        incident_conversation.convert_epoch_to_datetime_est(1583652000)
        == "2020-03-08 03:20:00 ET"
    )


def test_convert_epoch_to_datetime_est_current_epoch_time():
    time = MagicMock()
    time.return_value = 1609459200
    current_est = incident_conversation.convert_epoch_to_datetime_est(time)
    assert current_est == "1969-12-31 19:00:01 ET"


def test_convert_epoch_to_datetime_est_edge_cases():
    # Test with the epoch time at 0
    assert (
        incident_conversation.convert_epoch_to_datetime_est(0)
        == "1969-12-31 19:00:00 ET"
    )
    # Test with a very large epoch time, for example
    assert (
        incident_conversation.convert_epoch_to_datetime_est(32503680000)
        == "2999-12-31 19:00:00 ET"
    )


def test_handle_forwarded_messages_with_attachments():
    message = {
        "text": "Original message",
        "attachments": [
            {"fallback": "```Forwarded message 1```"},
            {"fallback": "Another forwarded message 2"},
        ],
    }
    updated_message = incident_conversation.handle_forwarded_messages(message)
    assert updated_message["text"] == (
        "Original message\nForwarded Message: Forwarded message 1\nForwarded Message: Another forwarded message 2"
    )


def test_handle_forwarded_messages_without_attachments():
    message = {
        "text": "Original message",
    }
    updated_message = incident_conversation.handle_forwarded_messages(message)
    assert updated_message["text"] == "Original message"


def test_handle_forwarded_messages_with_empty_attachments():
    message = {
        "text": "Original message",
        "attachments": [],
    }
    updated_message = incident_conversation.handle_forwarded_messages(message)
    assert updated_message["text"] == "Original message"


def test_handle_forwarded_messages_with_no_fallback():
    message = {
        "text": "Original message",
        "attachments": [
            {"no_fallback": "This attachment has no fallback"},
        ],
    }
    updated_message = incident_conversation.handle_forwarded_messages(message)
    assert updated_message["text"] == "Original message"


def test_handle_forwarded_messages_mixed_fallback():
    message = {
        "text": "Original message",
        "attachments": [
            {"fallback": "```Forwarded message 1```"},
            {"no_fallback": "This attachment has no fallback"},
            {"fallback": "Another ```forwarded``` message 2"},
        ],
    }
    updated_message = incident_conversation.handle_forwarded_messages(message)
    assert updated_message["text"] == (
        "Original message\nForwarded Message: Forwarded message 1\nForwarded Message: Another forwarded message 2"
    )


def test_handle_images_in_message_with_images():
    message = {
        "text": "Here is an image",
        "files": [{"url_private": "https://example.com/image1.png"}],
    }
    expected_message = {
        "text": "Here is an image\nImage: https://example.com/image1.png",
        "files": [{"url_private": "https://example.com/image1.png"}],
    }
    updated_message = incident_conversation.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_with_multiple_images():
    message = {
        "text": "Here are some images",
        "files": [
            {"url_private": "https://example.com/image1.png"},
            {"url_private": "https://example.com/image2.png"},
        ],
    }
    expected_message = {
        "text": "Here are some images\nImage: https://example.com/image1.png",
        "files": [
            {"url_private": "https://example.com/image1.png"},
            {"url_private": "https://example.com/image2.png"},
        ],
    }
    updated_message = incident_conversation.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_without_images():
    message = {
        "text": "No images here",
    }
    expected_message = {
        "text": "No images here",
    }
    updated_message = incident_conversation.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_no_files_key():
    message = {"text": "No files key here"}
    expected_message = {"text": "No files key here"}
    updated_message = incident_conversation.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_empty_text():
    message = {"text": "", "files": [{"url_private": "https://example.com/image1.png"}]}
    expected_message = {
        "text": "Image: https://example.com/image1.png",
        "files": [{"url_private": "https://example.com/image1.png"}],
    }
    updated_message = incident_conversation.handle_images_in_message(message)
    assert updated_message == expected_message


@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="dummy_document_id",
)
def test_get_incident_document_id_found(mock_extract):
    client = MagicMock()
    logger = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/12345",
            }
        ],
    }
    document_id = incident_conversation.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == "dummy_document_id"
    logger.error.assert_not_called()


@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="",
)
def test_get_incident_document_id_not_found(mock_extract):
    client = MagicMock()
    logger = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Other report",
                "link": "https://docs.google.com/document/d/67890",
            }
        ],
    }

    document_id = incident_conversation.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == ""
    mock_extract.assert_not_called()
    logger.error.assert_not_called()


@patch(
    "integrations.google_workspace.google_docs.extract_google_doc_id",
    return_value="",
)
def test_get_incident_document_id_extraction_fails(mock_extract):
    client = MagicMock()
    logger = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/12345",
            }
        ],
    }

    document_id = incident_conversation.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == ""
    mock_extract.assert_called_once_with("https://docs.google.com/document/d/12345")
    logger.error.assert_called_once_with("No incident document found for this channel.")


def test_get_incident_document_id_api_fails():
    client = MagicMock()
    logger = MagicMock()
    client.bookmarks_list.return_value = {"ok": False}

    document_id = incident_conversation.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == ""
    logger.error.assert_not_called()


def test_handle_reaction_added_floppy_disk_reaction_in_incident_channel():
    logger = MagicMock()
    mock_client = MagicMock()

    # Set up mock client and body to simulate the scenario
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }
    mock_client.users_profile_get.return_value = {"profile": {"real_name": "John Doe"}}
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {"title": "Incident report", "link": "https://docs.google.com/document/d/1"}
        ],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Assert the correct API calls were made
    mock_client.conversations_info.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()


def test_handle_reaction_added_non_incident_channel():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "general"}}

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Assert that certain actions are not performed for a non-incident channel
    mock_client.conversations_history.assert_not_called()


def test_handle_reaction_added_empty_message_list():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {"messages": []}

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Assert that the function tries to fetch replies when the message list is empty
    mock_client.conversations_replies.assert_not_called()


def test_handle_reaction_added_message_in_thread():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": True,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_replies.return_value = {
        "messages": [{"ts": "123456", "user": "U123456"}]
    }

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Assert that the function doe
    mock_client.conversations_replies.assert_called_once()


def test_handle_reaction_added_message_in_thread_return_top_message():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": True,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Parent test message",
                "ts": "1512085950.000216",
            },
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Child test message",
                "ts": "1512085950.000216",
            },
        ],
    }
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_replies.return_value = {
        "messages": [{"ts": "123456", "user": "U123456"}]
    }

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Assert that the function doe
    mock_client.conversations_replies.assert_called_once()


def test_handle_reaction_added_incident_report_document_not_found():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    # Simulate no incident report document found
    mock_client.bookmarks_list.return_value = {"ok": True, "bookmarks": []}

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    mock_client.users_profile_get.assert_not_called()


@patch("modules.incident.incident_conversation.replace_text_between_headings")
@patch("modules.incident.incident_conversation.rearrange_by_datetime_ascending")
@patch("modules.incident.incident_conversation.slack_users")
@patch("modules.incident.incident_conversation.handle_images_in_message")
@patch("modules.incident.incident_conversation.get_timeline_section")
@patch("modules.incident.incident_conversation.convert_epoch_to_datetime_est")
@patch("modules.incident.incident_conversation.handle_forwarded_messages")
@patch("modules.incident.incident_conversation.get_incident_document_id")
@patch("modules.incident.incident_conversation.return_messages")
def test_handle_reaction_added_processes_messages(
    mock_return_messages,
    mock_get_incident_document_id,
    mock_handle_forwarded_messages,
    mock_convert_epoch_to_datetime_est,
    mock_get_timeline_section,
    mock_handle_images_in_message,
    mock_slack_users,
    mock_rearrange_by_datetime_ascending,
    mock_replace_text_between_headings,
):
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_return_messages.return_value = {
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)
    mock_return_messages.assert_called_once()
    mock_get_incident_document_id.assert_called_once()
    mock_handle_forwarded_messages.assert_called_once()
    mock_convert_epoch_to_datetime_est.assert_called_once()
    mock_get_timeline_section.assert_called_once()
    mock_handle_images_in_message.assert_called_once()
    mock_slack_users.replace_user_id_with_handle.assert_called_once()
    mock_rearrange_by_datetime_ascending.assert_called_once()
    mock_replace_text_between_headings.assert_called_once()


def test_handle_reaction_added_adding_new_message_to_timeline():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Make assertion that the function calls the correct functions
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()


def test_handle_reaction_added_adding_new_message_to_timeline_user_handle():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "<U123ABC456> says Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Make assertion that the function calls the correct functions
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()


def test_handle_reaction_added_returns_link():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "<U123ABC456> says Sample test message",
                "ts": "1512085950.000216",
                "has_more": False,
            }
        ],
    }

    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/123456789",
            }
        ],
    }

    mock_client.chat_getPermalink.return_value = {
        "ok": "true",
        "channel": "C123456",
        "permalink": "https://example.com",
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Make assertion that the function calls the correct functions
    mock_client.conversations_info.assert_called_once()
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()
    mock_client.chat_getPermalink.assert_called_once()


def test_handle_reaction_added_forwarded_message():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "attachments": [{"fallback": "This is a forwarded message"}],
                "text": "Original message text",
                "ts": "1617556890.000100",
                "user": "U1234567890",
                "files": [{"url_private": "https://example.com/image.png"}],
            }
        ],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_added(mock_client, lambda: None, body, logger)

    # Make assertion that the function calls the correct functions
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()


def test_handle_reaction_removed_successful_message_removal():
    # Mock the client and logger
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.users_profile_get.return_value = {
        "profile": {"real_name": "John Doe", "display_name": "John"}
    }
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [{"title": "Incident report", "link": "http://example.com"}],
    }
    mock_client.get_timeline_section.return_value = "Sample test message"
    mock_client.replace_text_between_headings.return_value = True

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }

    incident_conversation.handle_reaction_removed(
        mock_client, lambda: None, body, logger
    )
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()


def test_handle_reaction_removed_successful_message_removal_user_id():
    # Mock the client and logger
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.users_profile_get.return_value = {
        "profile": {"real_name": "John Doe", "display_name": "John"}
    }
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [{"title": "Incident report", "link": "http://example.com"}],
    }
    mock_client.get_timeline_section.return_value = "Sample test message"
    mock_client.replace_text_between_headings.return_value = True

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }
    mock_client.conversations_history.return_value = {
        "ok": True,
        "has_more": False,
        "messages": [
            {
                "type": "message",
                "user": "U123ABC456",
                "text": "<U123ABC456> says Sample test message",
                "ts": "1512085950.000216",
            }
        ],
    }

    incident_conversation.handle_reaction_removed(
        mock_client, lambda: None, body, logger
    )
    mock_client.conversations_history.assert_called_once()
    mock_client.bookmarks_list.assert_called_once()
    mock_client.users_profile_get.assert_called_once()


def test_handle_reaction_removed_message_not_in_timeline():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.conversations_history.return_value = {
        "messages": [{"ts": "123456", "user": "U123456"}]
    }
    mock_client.users_profile_get.return_value = {"profile": {"real_name": "John Doe"}}
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [{"title": "Incident report", "link": "http://example.com"}],
    }
    mock_client.get_timeline_section.return_value = "Some existing content"
    mock_client.replace_text_between_headings.return_value = False

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    assert (
        incident_conversation.handle_reaction_removed(
            mock_client, lambda: None, body, logger
        )
        is None
    )


@patch("modules.incident.incident_conversation.replace_text_between_headings")
@patch("modules.incident.incident_conversation.rearrange_by_datetime_ascending")
@patch("modules.incident.incident_conversation.slack_users")
@patch("modules.incident.incident_conversation.handle_images_in_message")
@patch("modules.incident.incident_conversation.get_timeline_section")
@patch("modules.incident.incident_conversation.convert_epoch_to_datetime_est")
@patch("modules.incident.incident_conversation.handle_forwarded_messages")
@patch("modules.incident.incident_conversation.get_incident_document_id")
@patch("modules.incident.incident_conversation.return_messages")
def test_handle_reaction_removed_processes_messages(
    mock_return_messages,
    mock_get_incident_document_id,
    mock_handle_forwarded_messages,
    mock_convert_epoch_to_datetime_est,
    mock_get_timeline_section,
    mock_handle_images_in_message,
    mock_slack_users,
    mock_rearrange_by_datetime_ascending,
    mock_replace_text_between_headings,
):
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}

    mock_return_messages.return_value = [
        {
            "type": "message",
            "text": "Original message text",
            "ts": "1617556890.000100",
            "user": "U1234567890",
            "files": [{"url_private": "https://example.com/image.png"}],
        }
    ]
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    # Mock the return value of get_timeline_section
    mock_get_timeline_section.return_value = " ➡️ [2021-04-04 12:34:50](https://example.com/permalink) John Doe: Original message text\n"

    # Mock the return value of convert_epoch_to_datetime_est
    mock_convert_epoch_to_datetime_est.return_value = "2021-04-04 12:34:50"

    # Mock the return value of users_profile_get
    mock_client.users_profile_get.return_value = {"profile": {"real_name": "John Doe"}}

    # Mock the return value of chat_getPermalink
    mock_client.chat_getPermalink.return_value = {
        "permalink": "https://example.com/permalink"
    }

    # Mock the return value of slack_users.replace_user_id_with_handle
    mock_slack_users.replace_user_id_with_handle.return_value = "Original message text"

    assert (
        incident_conversation.handle_reaction_removed(
            mock_client, lambda: None, body, logger
        )
        is None
    )
    mock_return_messages.assert_called_once()
    mock_get_incident_document_id.assert_called_once()
    mock_handle_forwarded_messages.assert_called_once()
    mock_convert_epoch_to_datetime_est.assert_called_once()
    mock_get_timeline_section.assert_called_once()
    mock_handle_images_in_message.assert_called_once()
    mock_slack_users.replace_user_id_with_handle.assert_called_once()
    mock_rearrange_by_datetime_ascending.assert_not_called()
    mock_replace_text_between_headings.assert_called_once()


@patch("modules.incident.incident_conversation.return_messages")
def test_handle_reaction_removed_no_messages(mock_return_messages):
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}

    # Mock return_messages to return an empty list
    mock_return_messages.return_value = []

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    assert (
        incident_conversation.handle_reaction_removed(
            mock_client, lambda: None, body, logger
        )
        is None
    )
    mock_return_messages.assert_called_once()
    logger.warning.assert_called_once_with("No messages found")


@patch("modules.incident.incident_conversation.return_messages")
@patch("modules.incident.incident_conversation.get_timeline_section")
@patch("modules.incident.incident_conversation.get_incident_document_id")
@patch("modules.incident.incident_conversation.convert_epoch_to_datetime_est")
@patch("modules.incident.incident_conversation.handle_forwarded_messages")
@patch("modules.incident.incident_conversation.handle_images_in_message")
@patch("modules.incident.incident_conversation.slack_users.replace_user_id_with_handle")
def test_handle_reaction_removed_message_not_found(
    mock_replace_user_id_with_handle,
    mock_handle_images_in_message,
    mock_handle_forwarded_messages,
    mock_convert_epoch_to_datetime_est,
    mock_get_incident_document_id,
    mock_get_timeline_section,
    mock_return_messages,
):
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_info.return_value = {"channel": {"name": "incident-123"}}
    mock_client.users_profile_get.return_value = {"profile": {"real_name": "John Doe"}}
    mock_client.chat_getPermalink.return_value = {"permalink": "http://example.com"}

    # Mock return_messages to return a list with one message
    mock_return_messages.return_value = [
        {"ts": "123456", "user": "U123456", "text": "Test message"}
    ]
    mock_handle_forwarded_messages.return_value = {
        "ts": "123456",
        "user": "U123456",
        "text": "Test message",
    }
    mock_convert_epoch_to_datetime_est.return_value = "2023-10-01 12:00:00"
    mock_get_incident_document_id.return_value = "doc123"
    mock_get_timeline_section.return_value = "Some content without the message"

    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }

    incident_conversation.handle_reaction_removed(
        mock_client, lambda: None, body, logger
    )

    mock_return_messages.assert_called_once()
    logger.warning.assert_called_once_with("Message not found in the timeline")


def test_handle_reaction_removed_non_incident_channel_reaction_removal():
    mock_client = MagicMock()

    # Mock a non-incident channel
    mock_client.conversations_info.return_value = {"channel": {"name": "general"}}

    # Assert that the function does not proceed with reaction removal
    mock_client.conversations_history.assert_not_called()


def test_handle_reaction_removed_empty_message_list_handling():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_history.return_value = {"messages": []}
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }
    assert (
        incident_conversation.handle_reaction_removed(
            mock_client, lambda: None, body, logger
        )
        is None
    )


def test_handle_reaction_removed_forwarded_message():
    logger = MagicMock()
    mock_client = MagicMock()
    mock_client.conversations_history.return_value = {
        "attachments": [{"fallback": "This is a forwarded message"}],
        "text": "Original message text",
        "ts": "1617556890.000100",
        "user": "U1234567890",
        "files": [{"url_private": "https://example.com/image.png"}],
    }
    body = {
        "event": {
            "reaction": "floppy_disk",
            "item": {"channel": "C123456", "ts": "123456"},
        }
    }
    assert (
        incident_conversation.handle_reaction_removed(
            mock_client, lambda: None, body, logger
        )
        is None
    )


@patch("modules.incident.incident_conversation.incident_helper")
@patch("modules.incident.incident_conversation.log_to_sentinel")
def test_archive_channel_action_ignore(mock_log_to_sentinel, mock_incident_helper):
    client = MagicMock()
    body = {
        "actions": [{"value": "ignore"}],
        "channel": {"id": "channel_id", "name": "incident-2024-01-12-test"},
        "message_ts": "message_ts",
        "user": {"id": "user_id"},
    }
    ack = MagicMock()
    respond = MagicMock()
    incident_conversation.archive_channel_action(client, body, ack, respond)
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


@patch("modules.incident.incident_conversation.incident_helper")
@patch("modules.incident.incident_conversation.log_to_sentinel")
def test_archive_channel_action_archive(
    mock_log_to_sentinel,
    mock_incident_helper,
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
    incident_conversation.archive_channel_action(client, body, ack, respond)
    assert ack.call_count == 1
    mock_log_to_sentinel.assert_called_once_with("incident_channel_archived", body)
    mock_incident_helper.close_incident.assert_called_once_with(
        client, channel_info, ack, respond
    )


@patch("modules.incident.incident_conversation.schedule_retro")
@patch("modules.incident.incident_conversation.log_to_sentinel")
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
    incident_conversation.archive_channel_action(client, body, ack, MagicMock())
    assert ack.call_count == 1
    mock_schedule.schedule_incident_retro.assert_called_once_with(
        client, channel_info, ack
    )
    mock_log_to_sentinel.assert_called_once_with("incident_retro_scheduled", body)
