from unittest.mock import ANY, MagicMock, patch

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.spreadsheets import RANGE_NOT_FOUND, SheetCell
from modules.incident import incident_folder


@patch("modules.incident.incident_folder.SRE_INCIDENT_FOLDER", "SRE_INCIDENT_FOLDER")
@patch("modules.incident.incident_folder.incident_drive")
def test_list_incident_folders(incident_drive_mock):
    incident_drive_mock.list_child_folders.return_value = [{"id": "foo", "name": "bar"}]
    assert incident_folder.list_incident_folders() == [{"id": "foo", "name": "bar"}]
    incident_drive_mock.list_child_folders.assert_called_once_with("SRE_INCIDENT_FOLDER")


@patch("modules.incident.incident_folder.SRE_INCIDENT_FOLDER", "SRE_INCIDENT_FOLDER")
@patch("modules.incident.incident_folder.incident_drive")
def test_list_incident_folders_sorted(incident_drive_mock):
    incident_drive_mock.list_child_folders.return_value = [
        {"id": "baz", "name": "qux"},
        {"id": "foo", "name": "bar"},
    ]
    assert incident_folder.list_incident_folders() == [
        {"id": "foo", "name": "bar"},
        {"id": "baz", "name": "qux"},
    ]
    incident_drive_mock.list_child_folders.assert_called_once_with("SRE_INCIDENT_FOLDER")


@patch("modules.incident.incident_folder.SRE_INCIDENT_FOLDER", "SRE_INCIDENT_FOLDER")
@patch("modules.incident.incident_folder.incident_drive")
def test_list_incident_folders_truncates_to_the_display_limit(incident_drive_mock):
    """Drive listings are unbounded now, so the Slack option limit is enforced here."""
    limit = incident_folder.LEGACY_FOLDER_DISPLAY_LIMIT
    incident_drive_mock.list_child_folders.return_value = [{"id": str(i), "name": f"folder-{i:03d}"} for i in range(limit + 10)]

    result = incident_folder.list_incident_folders()

    assert len(result) == limit
    assert result[0]["name"] == "folder-000"
    assert result[-1]["name"] == f"folder-{limit - 1:03d}"


@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
@patch("modules.incident.incident_folder.folder_item")
def test_list_folders_view(folder_item_mock, list_child_folders_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    list_child_folders_mock.return_value = [{"id": "foo", "name": "bar"}]
    folder_item_mock.return_value = [["folder item"]]
    incident_folder.list_folders_view(client, body, ack)
    list_child_folders_mock.assert_called_once()
    folder_item_mock.assert_called_once_with({"id": "foo", "name": "bar"})
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)


@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
@patch("modules.incident.incident_folder.folder_item")
def test_list_folders_view_truncates_to_the_display_limit(folder_item_mock, list_child_folders_mock):
    """folder_item emits three blocks per folder, so the modal must stay under Slack's 100-block cap."""
    limit = incident_folder.LEGACY_FOLDER_DISPLAY_LIMIT
    client = MagicMock()
    ack = MagicMock()
    list_child_folders_mock.return_value = [{"id": str(i), "name": f"folder-{i:03d}"} for i in range(limit + 10)]
    folder_item_mock.return_value = [{"type": "section"}, {"type": "actions"}, {"type": "divider"}]

    incident_folder.list_folders_view(client, {"trigger_id": "foo"}, ack)

    assert folder_item_mock.call_count == limit
    assert len(client.views_open.call_args.kwargs["view"]["blocks"]) == limit * 3


@patch("modules.incident.incident_folder.logger")
@patch("modules.incident.incident_folder.incident_drive.delete_metadata")
@patch("modules.incident.incident_folder.view_folder_metadata")
def test_delete_folder_metadata(view_folder_metadata_mock, delete_metadata_mock, logger_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"private_metadata": "bar"}}
    ack = MagicMock()
    delete_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }
    incident_folder.delete_folder_metadata(client, body, ack)

    ack.assert_called_once()
    delete_metadata_mock.assert_called_once_with("bar", "foo")
    view_folder_metadata_mock.assert_called_once_with(
        client,
        {"actions": [{"value": "bar"}], "view": {"private_metadata": "bar"}},
        ack,
    )
    logger_mock.info.assert_called_once_with("metadata_delete_success", key="foo", folder_id="bar")


@patch("modules.incident.incident_folder.logger")
@patch("modules.incident.incident_folder.incident_drive.delete_metadata")
@patch("modules.incident.incident_folder.view_folder_metadata")
def test_delete_folder_metadata_failed(view_folder_metadata_mock, delete_metadata_mock, logger_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"private_metadata": "bar"}}
    ack = MagicMock()
    delete_metadata_mock.return_value = {}
    incident_folder.delete_folder_metadata(client, body, ack)

    ack.assert_called_once()
    delete_metadata_mock.assert_called_once_with("bar", "foo")
    view_folder_metadata_mock.assert_called_once_with(
        client,
        {"actions": [{"value": "bar"}], "view": {"private_metadata": "bar"}},
        ack,
    )
    logger_mock.warning.assert_called_once_with("metadata_delete_failed", key="foo", folder_id="bar")


@patch("modules.incident.incident_folder.incident_drive.add_metadata")
@patch("modules.incident.incident_folder.view_folder_metadata")
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
    incident_folder.save_metadata(client, body, ack, view)
    ack.assert_called_once()
    add_metadata_mock.assert_called_once_with("bar", "key", "value")
    view_folder_metadata_mock.assert_called_once_with(
        client,
        {"actions": [{"value": "bar"}]},
        ack,
    )


@patch("modules.incident.incident_folder.incident_drive")
def test_get_folder_metadata(incident_drive_mock):
    metadata = {
        "id": "folder_id",
        "name": "folder",
        "appProperties": {"key": "value"},
    }
    incident_drive_mock.get_metadata.return_value = metadata
    assert incident_folder.get_folder_metadata("foo") == metadata
    incident_drive_mock.get_metadata.assert_called_once_with("foo", fields="id, name, appProperties")


@patch("modules.incident.incident_folder.incident_drive.get_metadata")
@patch("modules.incident.incident_folder.metadata_items")
def test_view_folder_metadata_open(metadata_items_mock, get_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "trigger_id": "trigger_id"}
    ack = MagicMock()
    get_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_folder.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    get_metadata_mock.assert_called_once_with("foo", fields="id, name, appProperties")
    metadata_items_mock.assert_called_once_with({"name": "folder", "appProperties": [{"key": "key", "value": "value"}]})
    client.views_open(trigger_id="trigger_id", view=ANY)


@patch("modules.incident.incident_folder.incident_drive.get_metadata")
@patch("modules.incident.incident_folder.metadata_items")
def test_view_folder_metadata_update(metadata_items_mock, get_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"id": "view_id"}}
    ack = MagicMock()
    get_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_folder.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    get_metadata_mock.assert_called_once_with("foo", fields="id, name, appProperties")
    metadata_items_mock.assert_called_once_with({"name": "folder", "appProperties": [{"key": "key", "value": "value"}]})
    client.views_update(view_id="view_id", view=ANY)


def test_add_folder_metadata():
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"id": "bar"}}
    ack = MagicMock()
    incident_folder.add_folder_metadata(client, body, ack)
    ack.assert_called_once()
    client.views_update.assert_called_once_with(view_id="bar", view=ANY)


def test_folder_item():
    assert incident_folder.folder_item({"id": "foo", "name": "bar"}) == [
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
    assert incident_folder.metadata_items({}) == empty
    assert incident_folder.metadata_items({"appProperties": []}) == empty


def test_metadata_items():
    assert incident_folder.metadata_items({"appProperties": {"key": "value"}}) == [
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


class FakeSpreadsheetProvider:
    def __init__(self):
        self.read_values_result = OperationResult.success(data=[])
        self.update_values_result = OperationResult.success()
        self.append_values_result = OperationResult.success()
        self.read_cells_result = OperationResult.success(data=[])
        self.read_values_calls = []
        self.update_values_calls = []
        self.append_values_calls = []
        self.read_cells_calls = []

    def read_values(self, spreadsheet_id, a1_range):
        self.read_values_calls.append((spreadsheet_id, a1_range))
        return self.read_values_result

    def update_values(self, spreadsheet_id, a1_range, values):
        self.update_values_calls.append((spreadsheet_id, a1_range, values))
        return self.update_values_result

    def append_values(self, spreadsheet_id, a1_range, values):
        self.append_values_calls.append((spreadsheet_id, a1_range, values))
        return self.append_values_result

    def read_cells(self, spreadsheet_id, a1_range):
        self.read_cells_calls.append((spreadsheet_id, a1_range))
        return self.read_cells_result


@patch("modules.incident.incident_folder.INCIDENT_LIST", "INCIDENT_LIST")
@patch("modules.incident.incident_folder.datetime")
def test_add_new_incident_to_list_success(datetime_mock):
    provider = FakeSpreadsheetProvider()
    datetime_mock.datetime.now.return_value.strftime.return_value = "2021-01-01"
    document_link = "http://example.com"
    name = "foo"
    slug = "bar"
    product = "baz"
    channel_url = "http://channel.com"
    values = [
        [
            "2021-01-01",
            '=HYPERLINK("http://example.com", "foo")',
            "baz",
            "In Progress",
            '=HYPERLINK("http://channel.com", "#bar")',
        ],
    ]
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        assert incident_folder.add_new_incident_to_list(document_link, name, slug, product, channel_url)
    assert provider.append_values_calls == [("INCIDENT_LIST", "Sheet1!A:A", values)]


@patch("modules.incident.incident_folder.INCIDENT_LIST", "INCIDENT_LIST")
def test_add_new_incident_to_list_raises_on_failure():
    provider = FakeSpreadsheetProvider()
    provider.append_values_result = OperationResult.error(OperationStatus.TRANSIENT_ERROR, "write failed")
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        with pytest.raises(incident_folder.IncidentSheetError, match="write failed"):
            incident_folder.add_new_incident_to_list("doc", "name", "slug", "product", "channel")


@patch("modules.incident.incident_folder.logger")
def test_update_spreadsheet_incident_status_invalid_status(logger_mock):
    assert not incident_folder.update_spreadsheet_incident_status("foo", "InvalidStatus")
    logger_mock.warning.assert_called_once_with(
        "update_incident_spreadsheet_error",
        channel="foo",
        status="InvalidStatus",
        error="Invalid status",
    )


@patch("modules.incident.incident_folder.logger")
def test_update_spreadsheet_incident_status_empty_values(logger_mock):
    provider = FakeSpreadsheetProvider()
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        assert not incident_folder.update_spreadsheet_incident_status("foo", "Closed")
    logger_mock.warning.assert_called_once_with(
        "update_incident_spreadsheet_error",
        channel="foo",
        status="Closed",
        error="No values found in the sheet",
    )


def test_update_spreadsheet_incident_status_read_failure_raises():
    provider = FakeSpreadsheetProvider()
    provider.read_values_result = OperationResult.error(OperationStatus.TRANSIENT_ERROR, "read failed")
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        with pytest.raises(incident_folder.IncidentSheetError, match="read failed"):
            incident_folder.update_spreadsheet_incident_status("foo", "Closed")


@patch("modules.incident.incident_folder.INCIDENT_LIST", "INCIDENT_LIST")
def test_update_spreadsheet_incident_status_channel_found():
    provider = FakeSpreadsheetProvider()
    provider.read_values_result = OperationResult.success(data=[["foo", "bar", "baz", "qux"]])
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        assert incident_folder.update_spreadsheet_incident_status("foo", "Closed")
    assert provider.update_values_calls == [("INCIDENT_LIST", "Sheet1!D1", [["Closed"]])]


def test_update_spreadsheet_incident_status_update_failure_raises():
    provider = FakeSpreadsheetProvider()
    provider.read_values_result = OperationResult.success(data=[["foo"]])
    provider.update_values_result = OperationResult.error(OperationStatus.TRANSIENT_ERROR, "update failed")
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        with pytest.raises(incident_folder.IncidentSheetError, match="update failed"):
            incident_folder.update_spreadsheet_incident_status("foo", "Closed")


@patch("modules.incident.incident_folder.logger")
def test_update_spreadsheet_incident_status_channel_not_found(logger_mock):
    provider = FakeSpreadsheetProvider()
    provider.read_values_result = OperationResult.success(data=[["bar", "baz", "qux"]])
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        assert not incident_folder.update_spreadsheet_incident_status("foo", "Closed")
    logger_mock.warning.assert_called_once_with(
        "update_incident_spreadsheet_error",
        channel="foo",
        status="Closed",
        error="Channel not found in the sheet",
    )


def test_return_channel_name_with_prefix():
    # Test the function with a string that includes the prefix.
    assert incident_folder.return_channel_name("incident-abc123") == "#abc123"


def test_return_channel_name_with_dev_prefix():
    # Test the function with a string that includes the incident-dev prefix.
    assert incident_folder.return_channel_name("incident-dev-abc123") == "#abc123"


def test_return_channel_name_without_prefix():
    # Test the function with a string that does not include the prefix.
    assert incident_folder.return_channel_name("general") == "general"


def test_return_channel_name_empty_string():
    # Test the function with an empty string.
    assert incident_folder.return_channel_name("") == ""


def test_return_channel_name_prefix_only():
    # Test the function with a string that is only the prefix.
    assert incident_folder.return_channel_name("incident-") == "#"


def test_return_channel_name_dev_prefix_only():
    # Test the function with a string that is only the incident-dev prefix.
    assert incident_folder.return_channel_name("incident-dev-") == "#"


@pytest.mark.parametrize(
    ("channel_name", "expected"),
    [
        ("incident-abc123", "abc123"),
        ("incident-dev-abc123", "abc123"),
        ("general", "general"),
        ("", ""),
        ("incident-", ""),
        ("incident-dev-", ""),
    ],
)
def test_channel_slug(channel_name, expected):
    assert incident_folder.channel_slug(channel_name) == expected


@patch("modules.incident.incident_folder.dynamodb.scan")
@patch("modules.incident.incident_folder.dynamodb.update_item")
@patch("modules.incident.incident_folder.current_time_est")
def test_store_update(mock_current_time_est, mock_update_item, mock_scan_item):
    mock_current_time_est.return_value = "2025-01-31 11:17:06"
    mock_scan_item.return_value = [{"incident_updates": {"L": [{"S": "Previous update"}]}}]
    mock_update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    response = incident_folder.store_update("incident_id", "New update")
    assert response is not None
    mock_scan_item.assert_called_once()
    mock_update_item.assert_called_once()

    expected_update = "2025-01-31 11:17:06 EST\nNew update\nPrevious update"
    actual_updates = mock_update_item.call_args[1]["ExpressionAttributeValues"][":updates"]["L"]
    assert len(actual_updates) == 1
    assert actual_updates[0]["S"] == expected_update


@patch("modules.incident.incident_folder.dynamodb.scan")
@patch("modules.incident.incident_folder.dynamodb.update_item")
@patch("modules.incident.incident_folder.current_time_est")
def test_store_update_failed(mock_current_time_est, mock_update_item, mock_scan_item):
    mock_current_time_est.return_value = "2025-01-31 11:17:06"
    mock_scan_item.return_value = [{"incident_updates": {"L": [{"S": "Previous update"}]}}]
    mock_update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 400}}

    response = incident_folder.store_update("incident_id", "New update")
    assert response is None
    mock_scan_item.assert_called_once()
    mock_update_item.assert_called_once()


@patch("modules.incident.incident_folder.dynamodb.scan")
def test_fetch_updates(mock_scan_item):
    mock_scan_item.return_value = [{"incident_updates": {"L": [{"S": "Update 1\n Update 2"}]}}]

    updates = incident_folder.fetch_updates("incident_id")
    assert updates == ["Update 1\n Update 2"]

    # Test case when no updates are found
    mock_scan_item.return_value = {}
    updates = incident_folder.fetch_updates("incident_id")
    assert updates == []
    assert mock_scan_item.call_count == 2


def _incident_row_data():
    return [
        [SheetCell("header")],
        [
            SheetCell("2024-01-01"),
            SheetCell("Incident name", "https://report.example.com/doc"),
            SheetCell("Team A"),
            SheetCell("Closed"),
            SheetCell("#incident-2024-01-01-test", "https://gcdigital.slack.com/archives/C0123456789"),
        ],
    ]


def test_get_incidents_from_sheet_returns_parsed_incidents():
    provider = FakeSpreadsheetProvider()
    provider.read_cells_result = OperationResult.success(data=_incident_row_data())
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        incidents = incident_folder.get_incidents_from_sheet()

    assert incidents == [
        {
            "channel_id": "C0123456789",
            "channel_name": "incident-2024-01-01-test",
            "name": "Incident name",
            "user_id": "",
            "teams": ["Team A"],
            "report_url": "https://report.example.com/doc",
            "status": "Closed",
            "created_at": "2024-01-01",
            "meet_url": "TBC",
        }
    ]


@patch("modules.incident.incident_folder.logger")
def test_get_incidents_from_sheet_swallows_range_not_found(mock_logger):
    provider = FakeSpreadsheetProvider()
    provider.read_cells_result = OperationResult.error(
        OperationStatus.NOT_FOUND,
        "Unable to parse range: Sheet1",
        error_code=RANGE_NOT_FOUND,
    )
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        assert incident_folder.get_incidents_from_sheet() == []
    mock_logger.warning.assert_called_once()


def test_get_incidents_from_sheet_raises_on_other_failure():
    provider = FakeSpreadsheetProvider()
    provider.read_cells_result = OperationResult.error(OperationStatus.TRANSIENT_ERROR, "Internal error", error_code="X")
    with patch.object(incident_folder, "get_spreadsheet_provider", lambda: provider):
        with pytest.raises(incident_folder.IncidentSheetError, match="Internal error"):
            incident_folder.get_incidents_from_sheet()
