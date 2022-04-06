from commands.helpers import incident_helper


from unittest.mock import ANY, MagicMock, patch


def test_handle_incident_command_with_empty_args():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command([], MagicMock(), MagicMock(), respond, ack)
    respond.assert_called_once_with(incident_helper.help_text)


@patch("commands.helpers.incident_helper.google_drive.create_folder")
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


@patch("commands.helpers.incident_helper.list_folders")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(
        ["list-folders"], client, body, respond, ack
    )
    list_folders_mock.assert_called_once_with(client, body, ack)


@patch("commands.helpers.incident_helper.stale_incidents")
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


@patch("commands.helpers.incident_helper.google_drive.delete_metadata")
@patch("commands.helpers.incident_helper.view_folder_metadata")
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


@patch("commands.helpers.incident_helper.google_drive.list_folders")
@patch("commands.helpers.incident_helper.folder_item")
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


@patch("commands.helpers.incident_helper.google_drive.add_metadata")
@patch("commands.helpers.incident_helper.view_folder_metadata")
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


@patch("commands.helpers.incident_helper.get_stale_channels")
def test_stale_incidents(get_stale_channels_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    get_stale_channels_mock.return_value = [
        {"id": "id", "topic": {"value": "topic_value"}}
    ]
    incident_helper.stale_incidents(client, body, ack)
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)


@patch("commands.helpers.incident_helper.google_drive.list_metadata")
@patch("commands.helpers.incident_helper.metadata_items")
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


@patch("commands.helpers.incident_helper.google_drive.list_metadata")
@patch("commands.helpers.incident_helper.metadata_items")
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
