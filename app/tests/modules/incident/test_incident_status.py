from unittest.mock import MagicMock, call, patch
import pytest
from slack_sdk import WebClient
import uuid
from modules.incident import incident_status


@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.google_docs")
def test_update_status_success(
    mock_google_docs,
    mock_incident_document,
    mock_incident_folder,
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
    mock_incident_folder.update_incident_field.assert_not_called()
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_not_called()


@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.google_docs")
def test_update_status_success_with_incident_id(
    mock_google_docs,
    mock_incident_document,
    mock_incident_folder,
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
    mock_incident_folder.update_incident_field.assert_called_once_with(
        incident_id, "status", status
    )
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_not_called()


@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logging")
def test_update_status_handles_bookmarks_list_errors(
    mock_logging, mock_google_docs, mock_incident_folder, mock_incident_document
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

    calls = [
        call("Could not get bookmarks for channel incident-123: error_bookmarks"),
        call(
            "No bookmark link for the incident document found for channel incident-123"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logging.warning.assert_has_calls(calls)
    respond.assert_has_calls(calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logging")
def test_update_status_handles_update_document_errors(
    mock_logging, mock_google_docs, mock_incident_folder, mock_incident_document
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

    calls = [
        call(
            "Could not update the incident status in the document for channel incident-123: error_document"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logging.warning.assert_has_calls(calls)
    respond.assert_has_calls(calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


@patch("modules.incident.incident_status.incident_document")
@patch("modules.incident.incident_status.incident_folder")
@patch("modules.incident.incident_status.google_docs")
@patch("modules.incident.incident_status.logging")
def test_update_status_handles_update_spreadsheet_errors(
    mock_logging, mock_google_docs, mock_incident_folder, mock_incident_document
):
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = (
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
    mock_google_docs.extract_google_doc_id.return_value = "1234567890"
    mock_incident_folder.update_spreadsheet_incident_status.side_effect = Exception(
        "error_spreadsheet"
    )
    incident_status.update_status(
        client, respond, status, channel_id, channel_name, user_id
    )

    calls = [
        call(
            "Could not update the incident status in the spreadsheet for channel incident-123: error_spreadsheet"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    mock_logging.warning.assert_has_calls(calls)
    respond.assert_has_calls(calls)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )


def test_update_status_handles_chat_postMessage_errors():
    client = MagicMock(spec=WebClient)
    respond = MagicMock()
    status = "Reviewed"
    channel_id = "C123456"
    channel_name = "incident-123"
    user_id = "U123456"

    client.bookmarks_list.return_value = (
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

    calls = [
        call(
            "Could not post the incident status update to the channel incident-123: error_chat_postMessage"
        ),
    ]
    client.bookmarks_list.assert_called_once_with(channel_id=channel_id)
    client.chat_postMessage.assert_called_once_with(
        channel=channel_id,
        text=f"<@{user_id}> has updated the incident status to {status}.",
    )
    respond.assert_has_calls(calls)


@patch("modules.incident.incident_status.parse_incident_datetime_string")
@patch("modules.incident.incident_status.logging")
def test_incident_information_view(mock_logging, mock_parse_incident_datetime_string):
    incident_data = generate_incident_data()
    id = incident_data["id"]["S"]
    mock_parse_incident_datetime_string.side_effect = [
        "2025-01-23 17:02",
        "Unknown",
        "Unknown",
        "Unknown",
    ]
    view = incident_status.incident_information_view(incident_data)
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


@patch("modules.incident.incident_status.logging")
def test_update_field_view(mock_logging):
    view = incident_status.update_field_view("update_status")
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
        incident_status.parse_incident_datetime_string("2025-01-23 17:02:16.915368")
        == "2025-01-23 17:02"
    )
    assert (
        incident_status.parse_incident_datetime_string("2025-01-23 17:02") == "Unknown"
    )
    assert incident_status.parse_incident_datetime_string("") == "Unknown"
    assert incident_status.parse_incident_datetime_string("asdf") == "Unknown"
    with pytest.raises(TypeError):
        incident_status.parse_incident_datetime_string(None)


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
