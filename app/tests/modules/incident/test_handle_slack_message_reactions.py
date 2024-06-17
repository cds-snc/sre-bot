from unittest.mock import MagicMock, patch
from modules.incident import handle_slack_message_reactions


def test_multiline_entries_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Message one
    ➡️ [2024-03-05 18:24:30 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-05 18:24:30 ET](https://example.com/link2) Jane Smith: Message two\n\n\n➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Message one"
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(
            input_text
        ).strip()
        == expected_output
    )


def test_rearrange_single_entry():
    input_text = "➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Only one message"
    expected_output = "➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Only one message"
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(
            input_text
        ).strip()
        == expected_output
    )


def test_rearrange_no_entries():
    input_text = ""
    expected_output = ""
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(
            input_text
        ).strip()
        == expected_output
    )


def test_entries_out_of_order_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ [2024-03-07 11:00:00 ET](https://example.com/link1) John Doe: Message one
    ➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two\n\n\n➡️ [2024-03-07 11:00:00 ET](https://example.com/link1) John Doe: Message one"
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(
            input_text
        ).strip()
        == expected_output
    )


def test_invalid_entries_rearrange_by_datetime_ascending():
    input_text = """
    ➡️ Invalid Entry
    ➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two
    """
    expected_output = "➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two\n"
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text)
        == expected_output
    )


def test_empty_input_rearrange_by_datetime_ascending():
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending("") == ""


def test_no_datetime_entries_rearrange_by_datetime_ascending():
    input_text = "Message without datetime\nAnother message"
    assert (
        handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == ""
    )


def test_convert_epoch_to_datetime_est_known_epoch_time():
    # Example: 0 epoch time corresponds to 1969-12-31 19:00:00 EST
    assert (
        handle_slack_message_reactions.convert_epoch_to_datetime_est(0)
        == "1969-12-31 19:00:00 ET"
    )


def test_convert_epoch_to_datetime_est_daylight_saving_time_change():
    # Test with an epoch time known to fall in DST transition
    # For example, 1583652000 corresponds to 2020-03-08 03:20:00 EST
    assert (
        handle_slack_message_reactions.convert_epoch_to_datetime_est(1583652000)
        == "2020-03-08 03:20:00 ET"
    )


def test_convert_epoch_to_datetime_est_current_epoch_time():
    time = MagicMock()
    time.return_value = 1609459200
    current_est = handle_slack_message_reactions.convert_epoch_to_datetime_est(time)
    assert current_est == "1969-12-31 19:00:01 ET"


def test_convert_epoch_to_datetime_est_edge_cases():
    # Test with the epoch time at 0
    assert (
        handle_slack_message_reactions.convert_epoch_to_datetime_est(0)
        == "1969-12-31 19:00:00 ET"
    )
    # Test with a very large epoch time, for example
    assert (
        handle_slack_message_reactions.convert_epoch_to_datetime_est(32503680000)
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
    updated_message = handle_slack_message_reactions.handle_forwarded_messages(message)
    assert updated_message["text"] == (
        "Original message\nForwarded Message: Forwarded message 1\nForwarded Message: Another forwarded message 2"
    )


def test_handle_forwarded_messages_without_attachments():
    message = {
        "text": "Original message",
    }
    updated_message = handle_slack_message_reactions.handle_forwarded_messages(message)
    assert updated_message["text"] == "Original message"


def test_handle_forwarded_messages_with_empty_attachments():
    message = {
        "text": "Original message",
        "attachments": [],
    }
    updated_message = handle_slack_message_reactions.handle_forwarded_messages(message)
    assert updated_message["text"] == "Original message"


def test_handle_forwarded_messages_with_no_fallback():
    message = {
        "text": "Original message",
        "attachments": [
            {"no_fallback": "This attachment has no fallback"},
        ],
    }
    updated_message = handle_slack_message_reactions.handle_forwarded_messages(message)
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
    updated_message = handle_slack_message_reactions.handle_forwarded_messages(message)
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
    updated_message = handle_slack_message_reactions.handle_images_in_message(message)
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
    updated_message = handle_slack_message_reactions.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_without_images():
    message = {
        "text": "No images here",
    }
    expected_message = {
        "text": "No images here",
    }
    updated_message = handle_slack_message_reactions.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_no_files_key():
    message = {"text": "No files key here"}
    expected_message = {"text": "No files key here"}
    updated_message = handle_slack_message_reactions.handle_images_in_message(message)
    assert updated_message == expected_message


def test_handle_images_in_message_empty_text():
    message = {"text": "", "files": [{"url_private": "https://example.com/image1.png"}]}
    expected_message = {
        "text": "Image: https://example.com/image1.png",
        "files": [{"url_private": "https://example.com/image1.png"}],
    }
    updated_message = handle_slack_message_reactions.handle_images_in_message(message)
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
    document_id = handle_slack_message_reactions.get_incident_document_id(
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

    document_id = handle_slack_message_reactions.get_incident_document_id(
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

    document_id = handle_slack_message_reactions.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == ""
    mock_extract.assert_called_once_with("https://docs.google.com/document/d/12345")
    logger.error.assert_called_once_with("No incident document found for this channel.")


def test_get_incident_document_id_api_fails():
    client = MagicMock()
    logger = MagicMock()
    client.bookmarks_list.return_value = {"ok": False}

    document_id = handle_slack_message_reactions.get_incident_document_id(
        client, "channel_id", logger
    )
    assert document_id == ""
    logger.error.assert_not_called()
