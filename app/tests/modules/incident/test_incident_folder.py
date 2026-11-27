from unittest.mock import ANY, MagicMock, patch

import pytest

from contracts.operations import OperationResult
from infrastructure.spreadsheets import SheetCell
from modules.incident import incident_folder


@pytest.fixture
def logger_mock():
    with patch("modules.incident.incident_folder.logger") as mock:
        mock.bind.return_value = mock
        yield mock


def _view_client() -> MagicMock:
    client = MagicMock()
    client.views_open.return_value = {"view": {"id": "V_LOADING"}}
    return client


@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
@patch("modules.incident.incident_folder.folder_item")
def test_list_folders_view(folder_item_mock, list_child_folders_mock):
    """The loading modal opens before the Drive read, so the trigger_id is spent within Slack's 3 seconds."""
    client = _view_client()
    order: list[str] = []
    client.views_open.side_effect = lambda **kwargs: order.append("views_open") or {"view": {"id": "V_LOADING"}}
    list_child_folders_mock.side_effect = lambda folder_id: order.append("drive_read") or [{"id": "foo", "name": "bar"}]
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    folder_item_mock.return_value = [["folder item"]]

    incident_folder.list_folders_view(client, body, ack)

    assert order == ["views_open", "drive_read"]
    folder_item_mock.assert_called_once_with({"id": "foo", "name": "bar"})
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)
    assert "Loading" in str(client.views_open.call_args.kwargs["view"])
    client.views_update.assert_called_once_with(view_id="V_LOADING", view=ANY)
    assert client.views_update.call_args.kwargs["view"]["blocks"] == [["folder item"]]


@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
@patch("modules.incident.incident_folder.folder_item")
def test_list_folders_view_truncates_to_the_display_limit(folder_item_mock, list_child_folders_mock):
    """folder_item emits three blocks per folder, so the modal must stay under Slack's 100-block cap."""
    limit = incident_folder.LEGACY_FOLDER_DISPLAY_LIMIT
    client = _view_client()
    ack = MagicMock()
    list_child_folders_mock.return_value = [{"id": str(i), "name": f"folder-{i:03d}"} for i in range(limit + 10)]
    folder_item_mock.return_value = [{"type": "section"}, {"type": "actions"}, {"type": "divider"}]

    incident_folder.list_folders_view(client, {"trigger_id": "foo"}, ack)

    assert folder_item_mock.call_count == limit
    assert len(client.views_update.call_args.kwargs["view"]["blocks"]) == limit * 3


@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
def test_list_folders_view_with_no_folders_updates_to_a_message(list_child_folders_mock):
    """An empty or failed read (the adapter returns []) replaces the loading text with a message."""
    client = _view_client()
    list_child_folders_mock.return_value = []

    incident_folder.list_folders_view(client, {"trigger_id": "foo"}, MagicMock())

    view = client.views_update.call_args.kwargs["view"]
    assert client.views_update.call_args.kwargs["view_id"] == "V_LOADING"
    assert "No products could be listed" in view["blocks"][0]["text"]["text"]


@patch("modules.incident.incident_folder.logger")
@patch("modules.incident.incident_folder.incident_drive.list_child_folders")
def test_list_folders_view_drive_failure_updates_to_a_message_without_its_text(list_child_folders_mock, logger_mock):
    """A raised error (a refused credential) is logged by type and never shown or logged as text."""
    client = _view_client()
    list_child_folders_mock.side_effect = RuntimeError("folder 1AbCsecret unreachable")

    incident_folder.list_folders_view(client, {"trigger_id": "foo"}, MagicMock())

    view = client.views_update.call_args.kwargs["view"]
    assert "No products could be listed" in view["blocks"][0]["text"]["text"]
    assert "1AbCsecret" not in str(view)
    logger_mock.error.assert_called_once_with("incident_folders_list_failed", error_type="RuntimeError")


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
