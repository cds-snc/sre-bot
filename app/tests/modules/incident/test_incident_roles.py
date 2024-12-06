import json
from unittest.mock import MagicMock, patch, ANY
from modules.incident import incident_roles as incident_helper


@patch("modules.incident.incident_roles.google_drive.find_files_by_name")
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


@patch("modules.incident.incident_roles.google_drive.find_files_by_name")
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


@patch("modules.incident.incident_roles.google_drive.find_files_by_name")
def test_manage_roles_with_dev_prefix(get_document_by_channel_name_mock):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-dev-channel_name",
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


@patch("modules.incident.incident_roles.google_drive.add_metadata")
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
