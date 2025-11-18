"""Tests for recreate_missing_resources functionality."""

from unittest.mock import MagicMock, patch, call
import pytest
from modules.incident import core


@pytest.fixture
def mock_client():
    """Create a mock Slack WebClient."""
    client = MagicMock()
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {
            "id": "C123456",
            "name": "incident-2024-001",
            "topic": {
                "value": "Incident: Test Incident / Test Product",
            },
            "created": 1234567890,
        },
    }
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [],
    }
    return client


@pytest.fixture
def basic_params():
    """Basic parameters for recreate_missing_resources."""
    return {
        "channel_id": "C123456",
        "channel_name": "incident-2024-001",
        "user_id": "U123456",
    }


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.on_call")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.google_drive")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_all_missing(
    mock_logger,
    mock_google_drive,
    mock_meet,
    mock_on_call,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test recreating all resources when everything is missing."""
    # Setup mocks
    mock_db_operations.get_incident_by_channel_id.return_value = None
    mock_incident_folder.list_incident_folders.return_value = [
        {"id": "folder_123", "name": "Test Product"}
    ]
    mock_google_drive.list_files_in_folder.return_value = []
    mock_incident_document.create_incident_document.return_value = "doc_123"
    mock_on_call.get_on_call_users_from_folder.return_value = [
        {
            "id": "U999",
            "profile": {"display_name_normalized": "On Call User"},
        }
    ]
    mock_meet.create_space.return_value = {
        "meetingUri": "https://meet.google.com/test-meet"
    }
    mock_incident_folder.get_incidents_from_sheet.return_value = []
    mock_db_operations.create_incident.return_value = "incident_id_123"

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify all resources were created
    assert len(results["success"]) >= 4  # Meet, Doc, Sheet, DB
    assert len(results["errors"]) == 0
    assert "Meet link" in str(results["success"])
    assert "incident document" in str(results["success"])
    assert "Google Sheets" in str(results["success"])
    assert "database record" in str(results["success"])

    # Verify Meet link was created
    mock_meet.create_space.assert_called_once()
    mock_client.bookmarks_add.assert_any_call(
        channel_id=basic_params["channel_id"],
        title="Meet link",
        type="link",
        link="https://meet.google.com/test-meet",
    )

    # Verify document was created
    mock_incident_document.create_incident_document.assert_called_once()
    mock_client.bookmarks_add.assert_any_call(
        channel_id=basic_params["channel_id"],
        title="Incident report",
        type="link",
        link="https://docs.google.com/document/d/doc_123/edit",
    )

    # Verify incident was added to sheet
    mock_incident_folder.add_new_incident_to_list.assert_called_once()

    # Verify database record was created
    mock_db_operations.create_incident.assert_called_once()


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.on_call")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.google_drive")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_all_exist(
    mock_logger,
    mock_google_drive,
    mock_meet,
    mock_on_call,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test when all resources already exist."""
    # Setup mocks - all resources exist
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Meet link",
                "link": "https://meet.google.com/existing-meet",
            },
            {
                "title": "Incident report",
                "link": "https://docs.google.com/document/d/existing_doc/edit",
            },
        ],
    }
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "existing_incident"},
        "channel_id": {"S": basic_params["channel_id"]},
    }
    mock_incident_folder.get_incidents_from_sheet.return_value = [
        {
            "channel_id": basic_params["channel_id"],
            "channel_name": basic_params["channel_name"],
        }
    ]

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify nothing was created
    assert len(results["success"]) == 0
    assert len(results["skipped"]) >= 3  # Meet, Doc, DB
    assert len(results["errors"]) == 0

    # Verify no creation calls were made
    mock_meet.create_space.assert_not_called()
    mock_incident_document.create_incident_document.assert_not_called()
    mock_db_operations.create_incident.assert_not_called()


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.on_call")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.google_drive")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_partial_missing(
    mock_logger,
    mock_google_drive,
    mock_meet,
    mock_on_call,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test when only some resources are missing."""
    # Setup mocks - only document bookmark is missing
    mock_client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {
                "title": "Meet link",
                "link": "https://meet.google.com/existing-meet",
            },
        ],
    }
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "existing_incident"},
        "channel_id": {"S": basic_params["channel_id"]},
    }
    mock_incident_folder.list_incident_folders.return_value = [
        {"id": "folder_123", "name": "Test Product"}
    ]
    mock_google_drive.list_files_in_folder.return_value = [
        {"id": "existing_doc_123", "name": "2024-001 Incident Report"}
    ]
    mock_incident_folder.get_incidents_from_sheet.return_value = []

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify only missing resources were created
    assert len(results["success"]) >= 2  # Found doc + Sheet
    assert len(results["skipped"]) >= 2  # Meet + DB
    assert "Meet link" in str(results["skipped"])
    assert "Database record" in str(results["skipped"])

    # Verify document was found but not created
    mock_incident_document.create_incident_document.assert_not_called()
    # Verify bookmark was added
    mock_client.bookmarks_add.assert_called()


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_channel_info_error(
    mock_logger,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test error handling when channel info cannot be retrieved."""
    # Setup mock to fail
    mock_client.conversations_info.return_value = {"ok": False}

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify error was captured
    assert len(results["errors"]) >= 1
    assert "channel information" in str(results["errors"]).lower()
    assert len(results["success"]) == 0


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.on_call")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.google_drive")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_unknown_product(
    mock_logger,
    mock_google_drive,
    mock_meet,
    mock_on_call,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test when product folder cannot be found."""
    # Setup mocks
    mock_db_operations.get_incident_by_channel_id.return_value = None
    mock_incident_folder.list_incident_folders.return_value = [
        {"id": "folder_999", "name": "Different Product"}
    ]
    mock_meet.create_space.return_value = {
        "meetingUri": "https://meet.google.com/test-meet"
    }

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify Meet was created but document creation failed
    assert "Meet link" in str(results["success"])
    assert "product folder not found" in str(results["errors"]).lower()

    # Meet should still be created
    mock_meet.create_space.assert_called_once()
    # But document creation should be skipped
    mock_incident_document.create_incident_document.assert_not_called()


@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.on_call")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.google_drive")
@patch("modules.incident.core.logger")
def test_recreate_missing_resources_meet_creation_fails(
    mock_logger,
    mock_google_drive,
    mock_meet,
    mock_on_call,
    mock_incident_document,
    mock_incident_folder,
    mock_db_operations,
    mock_client,
    basic_params,
):
    """Test when Meet link creation fails."""
    # Setup mocks
    mock_db_operations.get_incident_by_channel_id.return_value = None
    mock_meet.create_space.side_effect = Exception("Meet API error")

    # Execute
    results = core.recreate_missing_resources(
        mock_client,
        basic_params["channel_id"],
        basic_params["channel_name"],
        basic_params["user_id"],
    )

    # Verify error was captured but execution continued
    assert "Meet link" in str(results["errors"])
    assert "Meet API error" in str(results["errors"])

    # Other resources might still be created
    mock_logger.error.assert_called()
