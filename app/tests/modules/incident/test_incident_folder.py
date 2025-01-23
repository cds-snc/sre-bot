from unittest.mock import patch, MagicMock, ANY

from modules.incident import incident_folder


@patch("modules.incident.incident_folder.SRE_INCIDENT_FOLDER", "SRE_INCIDENT_FOLDER")
@patch("modules.incident.incident_folder.google_drive")
def test_list_incident_folders(google_drive_mock):
    google_drive_mock.list_folders_in_folder.return_value = [
        {"id": "foo", "name": "bar"}
    ]
    assert incident_folder.list_incident_folders() == [{"id": "foo", "name": "bar"}]
    google_drive_mock.list_folders_in_folder.assert_called_once_with(
        "SRE_INCIDENT_FOLDER", "not name contains 'Templates'"
    )


@patch("modules.incident.incident_folder.SRE_INCIDENT_FOLDER", "SRE_INCIDENT_FOLDER")
@patch("modules.incident.incident_folder.google_drive")
def test_list_incident_folders_sorted(google_drive_mock):
    google_drive_mock.list_folders_in_folder.return_value = [
        {"id": "baz", "name": "qux"},
        {"id": "foo", "name": "bar"},
    ]
    assert incident_folder.list_incident_folders() == [
        {"id": "foo", "name": "bar"},
        {"id": "baz", "name": "qux"},
    ]
    google_drive_mock.list_folders_in_folder.assert_called_once_with(
        "SRE_INCIDENT_FOLDER", "not name contains 'Templates'"
    )


@patch("modules.incident.incident_folder.google_drive.list_folders_in_folder")
@patch("modules.incident.incident_folder.folder_item")
def test_list_folders_view(folder_item_mock, list_folders_in_folder_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    list_folders_in_folder_mock.return_value = [{"id": "foo", "name": "bar"}]
    folder_item_mock.return_value = [["folder item"]]
    incident_folder.list_folders_view(client, body, ack)
    list_folders_in_folder_mock.assert_called_once()
    folder_item_mock.assert_called_once_with({"id": "foo", "name": "bar"})
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)


@patch("modules.incident.incident_folder.logging")
@patch("modules.incident.incident_folder.google_drive.delete_metadata")
@patch("modules.incident.incident_folder.view_folder_metadata")
def test_delete_folder_metadata(
    view_folder_metadata_mock, delete_metadata_mock, logging_mock
):
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
    logging_mock.info.assert_called_once_with("Deleted metadata for key `foo`")


@patch("modules.incident.incident_folder.logging")
@patch("modules.incident.incident_folder.google_drive.delete_metadata")
@patch("modules.incident.incident_folder.view_folder_metadata")
def test_delete_folder_metadata_failed(
    view_folder_metadata_mock, delete_metadata_mock, logging_mock
):
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
    logging_mock.info.assert_called_once_with(
        "Failed to delete metadata `foo` for folder `bar`"
    )


@patch("modules.incident.incident_folder.google_drive.add_metadata")
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


@patch("modules.incident.incident_folder.google_drive")
def test_get_folder_metadata(google_drive_mock):
    metadata = {
        "id": "folder_id",
        "name": "folder",
        "appProperties": {"key": "value"},
    }
    google_drive_mock.list_metadata.return_value = metadata
    assert incident_folder.get_folder_metadata("foo") == metadata
    google_drive_mock.list_metadata.assert_called_once_with("foo")


@patch("modules.incident.incident_folder.google_drive.list_metadata")
@patch("modules.incident.incident_folder.metadata_items")
def test_view_folder_metadata_open(metadata_items_mock, list_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "trigger_id": "trigger_id"}
    ack = MagicMock()
    list_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_folder.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    list_metadata_mock.assert_called_once_with("foo")
    metadata_items_mock.assert_called_once_with(
        {"name": "folder", "appProperties": [{"key": "key", "value": "value"}]}
    )
    client.views_open(trigger_id="trigger_id", view=ANY)


@patch("modules.incident.incident_folder.google_drive.list_metadata")
@patch("modules.incident.incident_folder.metadata_items")
def test_view_folder_metadata_update(metadata_items_mock, list_metadata_mock):
    client = MagicMock()
    body = {"actions": [{"value": "foo"}], "view": {"id": "view_id"}}
    ack = MagicMock()
    list_metadata_mock.return_value = {
        "name": "folder",
        "appProperties": [{"key": "key", "value": "value"}],
    }

    metadata_items_mock.return_value = [["metadata item"]]
    incident_folder.view_folder_metadata(client, body, ack)
    ack.assert_called_once()
    list_metadata_mock.assert_called_once_with("foo")
    metadata_items_mock.assert_called_once_with(
        {"name": "folder", "appProperties": [{"key": "key", "value": "value"}]}
    )
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


@patch("modules.incident.incident_folder.INCIDENT_LIST", "INCIDENT_LIST")
@patch("modules.incident.incident_folder.datetime")
@patch("modules.incident.incident_folder.sheets")
def test_add_new_incident_to_list(sheets_mock, datetime_mock):
    datetime_mock.datetime.now.return_value.strftime.return_value = "2021-01-01"
    document_link = "http://example.com"
    name = "foo"
    slug = "bar"
    product = "baz"
    channel_url = "http://channel.com"
    body = {
        "majorDimension": "ROWS",
        "values": [
            [
                "2021-01-01",
                '=HYPERLINK("http://example.com", "foo")',
                "baz",
                "In Progress",
                '=HYPERLINK("http://channel.com", "#bar")',
            ]
        ],
    }
    sheets_mock.append_values.return_value = ANY
    updated_sheet = incident_folder.add_new_incident_to_list(
        document_link, name, slug, product, channel_url
    )
    sheets_mock.append_values.assert_called_once_with(
        "INCIDENT_LIST",
        "Sheet1!A:A",
        body,
    )
    assert updated_sheet == ANY


@patch("modules.incident.incident_folder.sheets")
@patch("modules.incident.incident_folder.logging")
def test_update_spreadsheet_incident_status_invalid_status(logging_mock, sheets_mock):
    assert not incident_folder.update_spreadsheet_incident_status(
        "foo", "InvalidStatus"
    )
    logging_mock.warning.assert_called_once_with("Invalid status %s", "InvalidStatus")


@patch("modules.incident.incident_folder.sheets")
@patch("modules.incident.incident_folder.logging")
def test_update_spreadsheet_incident_status_empty_values(logging_mock, sheets_mock):
    sheets_mock.get_values.return_value = {"values": []}
    assert not incident_folder.update_spreadsheet_incident_status("foo", "Closed")
    logging_mock.warning.assert_called_once_with(
        "No incident found for channel %s", "foo"
    )


@patch("modules.incident.incident_folder.INCIDENT_LIST", "INCIDENT_LIST")
@patch("modules.incident.incident_folder.sheets")
def test_update_spreadsheet_incident_status_channel_found(sheets_mock):
    sheets_mock.get_values.return_value = {"values": [["foo", "bar", "baz", "qux"]]}
    sheets_mock.batch_update_values.return_value = True
    assert incident_folder.update_spreadsheet_incident_status("foo", "Closed")
    sheets_mock.batch_update_values.assert_called_once_with(
        "INCIDENT_LIST", "Sheet1!D1", [["Closed"]]
    )


@patch("modules.incident.incident_folder.sheets")
def test_update_spreadsheet_incident_status_channel_not_found(sheets_mock):
    sheets_mock.get_values.return_value = {"values": [["bar", "baz", "qux"]]}
    assert not incident_folder.update_spreadsheet_incident_status("foo", "Closed")


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


@patch("modules.incident.incident_folder.uuid")
@patch("modules.incident.incident_folder.datetime")
@patch("modules.incident.incident_folder.dynamodb")
def test_create_incident(mock_dynamodb, mock_datetime, mock_uuid):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value = (
        "2025-01-22 21:58:18.689313"
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert incident_folder.create_incident(
        "channel_id", "channel_name", "user_id", ["teams"], "report_url", "meet_url"
    )
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "prod"},
        },
    )


@patch("modules.incident.incident_folder.uuid")
@patch("modules.incident.incident_folder.datetime")
@patch("modules.incident.incident_folder.dynamodb")
def test_create_incident_with_optional_args(mock_dynamodb, mock_datetime, mock_uuid):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value = (
        "2025-01-22 21:58:18.689313"
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert incident_folder.create_incident(
        "channel_id",
        "channel_name",
        "user_id",
        ["teams"],
        "report_url",
        "meet_url",
        "start_time",
        "end_time",
        "detection_time",
        "retro_url",
        "dev",
    )
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "dev"},
            "start_impact_time": {"S": "start_time"},
            "end_impact_time": {"S": "end_time"},
            "detection_time": {"S": "detection_time"},
            "retrospective_url": {"S": "retro_url"},
        },
    )


@patch("modules.incident.incident_folder.uuid")
@patch("modules.incident.incident_folder.datetime")
@patch("modules.incident.incident_folder.dynamodb")
def test_create_incident_handle_error(mock_dynamodb, mock_datetime, mock_uuid):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value = (
        "2025-01-22 21:58:18.689313"
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 400}}
    response = incident_folder.create_incident(
        "channel_id", "channel_name", "user_id", ["teams"], "report_url", "meet_url"
    )
    assert response is None
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "prod"},
        },
    )


@patch("modules.incident.incident_folder.dynamodb")
def test_list_incidents(
    mock_dynamodb,
):
    mock_dynamodb.scan.return_value = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]
    assert incident_folder.list_incidents() == [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]


@patch("modules.incident.incident_folder.dynamodb")
def test_list_incidents_empty(
    mock_dynamodb,
):
    mock_dynamodb.scan.return_value = []
    assert incident_folder.list_incidents() == []


@patch("modules.incident.incident_folder.dynamodb")
def test_update_incident_field(mock_dynamodb):
    mock_dynamodb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert incident_folder.update_incident_field("foo", "bar", "baz")
    mock_dynamodb.update_item.assert_called_once_with(
        TableName="incidents",
        Key={"id": {"S": "foo"}},
        UpdateExpression="SET #bar = :bar",
        ExpressionAttributeNames={"#bar": "bar"},
        ExpressionAttributeValues={":bar": {"S": "baz"}},
    )


@patch("modules.incident.incident_folder.dynamodb")
def test_update_incident_field_with_type(mock_dynamodb):
    mock_dynamodb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert incident_folder.update_incident_field("foo", "bar", "baz", "M")
    mock_dynamodb.update_item.assert_called_once_with(
        TableName="incidents",
        Key={"id": {"S": "foo"}},
        UpdateExpression="SET #bar = :bar",
        ExpressionAttributeNames={"#bar": "bar"},
        ExpressionAttributeValues={":bar": {"M": "baz"}},
    )


@patch("modules.incident.incident_folder.dynamodb")
def test_update_incident_field_handles_failure(mock_dynamodb):
    mock_dynamodb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 400}
    }
    response = incident_folder.update_incident_field("foo", "bar", "baz")
    assert response is None


@patch("modules.incident.incident_folder.dynamodb")
def test_get_incident(mock_dynamodb):
    mock_dynamodb.get_item.return_value = {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
        "user_id": {"S": "qux"},
        "teams": {"SS": ["quux"]},
        "report_url": {"S": "corge"},
        "meet_url": {"S": "grault"},
        "status": {"S": "garply"},
        "start_impact_time": {"S": "waldo"},
        "end_impact_time": {"S": "fred"},
        "environment": {"S": "plugh"},
        "retrospective_url": {"S": "xyzzy"},
    }

    assert incident_folder.get_incident("foo") == {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
        "user_id": {"S": "qux"},
        "teams": {"SS": ["quux"]},
        "report_url": {"S": "corge"},
        "meet_url": {"S": "grault"},
        "status": {"S": "garply"},
        "start_impact_time": {"S": "waldo"},
        "end_impact_time": {"S": "fred"},
        "environment": {"S": "plugh"},
        "retrospective_url": {"S": "xyzzy"},
    }


@patch("modules.incident.incident_folder.dynamodb")
def test_lookup_incident(
    mock_dynamodb,
):
    incidents = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        },
    ]
    mock_dynamodb.scan.return_value = incidents
    assert incident_folder.lookup_incident("channel_id", "bar") == [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]

    mock_dynamodb.scan.assert_called_once_with(
        TableName="incidents",
        FilterExpression="channel_id = :channel_id",
        ExpressionAttributeValues={":channel_id": {"S": "bar"}},
    )
