from unittest.mock import MagicMock, call, patch
from slack_sdk import WebClient
from modules.incident import incident_status


@patch("modules.incident.incident_status.logger")
@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.google_docs")
def test_update_status_success(
    mock_google_docs,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_logger,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/1234567890/edit",
            }
        ],
    }
    mock_google_docs.extract_google_doc_id.return_value = "1234567890"
    mock_incident_folder.update_spreadsheet_incident_status.return_value = True
    mock_incident_folder.return_channel_name.return_value = "123"

    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )

    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_google_docs.extract_google_doc_id.assert_called_once_with(
        "https://docs.google.com/document/d/1234567890/edit"
    )
    mock_incident_document.update_incident_document_status.assert_called_once_with(
        "1234567890", status
    )

    mock_incident_folder.update_spreadsheet_incident_status.assert_called_once_with(
        mock_incident_folder.return_channel_name.return_value, status
    )
    mock_db_operations.update_incident_field.assert_not_called()
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_not_called()
    mock_logger.warning.assert_not_called()


@patch("modules.incident.incident_status.logger")
@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.google_docs")
def test_update_status_success_with_incident_id(
    mock_google_docs,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_logger,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"
    incident_id = "375e7b21-01a0-422e-a626-bbeacc419bad"

    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/1234567890/edit",
            }
        ],
    }
    mock_google_docs.extract_google_doc_id.return_value = "1234567890"
    mock_incident_folder.update_spreadsheet_incident_status.return_value = True
    mock_incident_folder.return_channel_name.return_value = "123"

    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id, incident_id
    )

    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_google_docs.extract_google_doc_id.assert_called_once_with(
        "https://docs.google.com/document/d/1234567890/edit"
    )
    mock_incident_document.update_incident_document_status.assert_called_once_with(
        "1234567890", status
    )

    mock_incident_folder.update_spreadsheet_incident_status.assert_called_once_with(
        mock_incident_folder.return_channel_name.return_value, status
    )
    mock_db_operations.update_incident_field.assert_called_once_with(
        incident_id, "status", status, user_id
    )
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_not_called()


@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logger")
def test_update_status_handles_bookmarks_list_errors(
    mock_logger,
    mock_google_docs,
    mock_incident_folder,
    mock_incident_document,
    mock_db_operations,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.side_effect = (Exception("error_bookmarks"),)

    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )

    logger_calls = [
        call(
            "incident_channel_bookmarks_not_found",
            channel="incident-123",
            error="error_bookmarks",
        ),
        call("incident_document_bookmark_not_found", channel="incident-123"),
    ]

    # Respond calls as formatted strings for Slack user
    respond_calls = [
        call("Could not get bookmarks for channel incident-123: error_bookmarks"),
        call(
            "No bookmark link for the incident document found for channel incident-123"
        ),
    ]

    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logger.warning.assert_has_calls(logger_calls)
    respond.assert_has_calls(respond_calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logger")
def test_update_status_handles_update_document_errors(
    mock_logger,
    mock_google_docs,
    mock_incident_folder,
    mock_incident_document,
    mock_db_operations,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/1234567890/edit",
            }
        ],
    }
    mock_google_docs.extract_google_doc_id.return_value = "1234567890"
    mock_incident_document.update_incident_document_status.side_effect = Exception(
        "error_document"
    )
    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )
    logger_calls = [
        call(
            "incident_document_status_update_failed",
            channel="incident-123",
            error="error_document",
        )
    ]
    respond_calls = [
        call(
            "Could not update the incident status in the document for channel incident-123: error_document"
        )
    ]

    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logger.warning.assert_has_calls(logger_calls)
    respond.assert_has_calls(respond_calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logger")
def test_update_status_handles_update_spreadsheet_errors(
    mock_logger,
    mock_google_docs,
    mock_incident_folder,
    mock_incident_document,
    mock_db_operations,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = dict(
        {
            "ok": True,
            "bookmarks": [
                {
                    "title": "Incident report",
                    "link": "https://docs.google.com/document/d/1234567890/edit",
                }
            ],
        }
    )

    mock_google_docs.extract_google_doc_id.return_value = "1234567890"
    mock_incident_folder.update_spreadsheet_incident_status.side_effect = Exception(
        "error_spreadsheet"
    )
    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )
    logger_calls = [
        call(
            "incident_folder_status_update_failed",
            channel="incident-123",
            error="error_spreadsheet",
        ),
    ]
    respond_calls = [
        call(
            "Could not update the incident status in the spreadsheet for channel incident-123: error_spreadsheet"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logger.warning.assert_has_calls(logger_calls)
    respond.assert_has_calls(respond_calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


@patch("modules.incident.incident_status.db_operations")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logger")
def test_update_status_handles_chat_postMessage_errors(
    mock_logger,
    mock_google_docs,
    mock_incident_folder,
    mock_incident_document,
    mock_db_operations,
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = dict(
        {
            "ok": True,
            "bookmarks": [
                {
                    "title": "Incident report",
                    "link": "https://docs.google.com/document/d/1234567890/edit",
                }
            ],
        },
    )
    client.chat_postMessage.side_effect = Exception("error_chat_postMessage")
    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )

    logger_calls = [
        call(
            "incident_status_update_post_failed",
            channel="incident-123",
            error="error_chat_postMessage",
        ),
    ]

    respond_calls = [
        call(
            "Could not post the incident status update to the channel incident-123: error_chat_postMessage"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_has_calls(respond_calls)

    mock_logger.warning.assert_has_calls(logger_calls)
