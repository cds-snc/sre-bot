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
    client.conversations_info.return_value = {
        "channel": {"purpose": {"value": "Existing purpose text"}}
    }
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
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id",
        purpose="Existing purpose text \nIC: <@selected_ic> / OL: <@selected_ol>",
    )


@patch("modules.incident.incident_roles.google_drive.add_metadata")
def test_save_incident_roles_append_purpose(add_metadata_mock):
    """If the channel purpose does NOT have existing IC/OL roles,
    it should append them (including leading newline)."""
    client = MagicMock()
    ack = MagicMock()
    # Mock .conversations_info to return a channel purpose with no existing IC/OL text
    client.conversations_info.return_value = {
        "channel": {"purpose": {"value": "Current channel purpose with no roles."}}
    }

    view = {
        "private_metadata": json.dumps(
            {
                "ic_id": "old_ic",
                "ol_id": "old_ol",
                "id": "file_id",
                "channel_id": "channel_id",
            }
        ),
        "state": {
            "values": {
                "ic_name": {"ic_select": {"selected_user": "new_ic"}},
                "ol_name": {"ol_select": {"selected_user": "new_ol"}},
            }
        },
    }

    incident_helper.save_incident_roles(client, ack, view)

    # Verify we ack the request
    ack.assert_called_once()
    # add_metadata is called for both IC and OL
    add_metadata_mock.assert_any_call("file_id", "ic_id", "new_ic")
    add_metadata_mock.assert_any_call("file_id", "ol_id", "new_ol")

    # Verify chat_postMessage was called for both role changes
    client.chat_postMessage.assert_any_call(
        text="<@new_ic> has been assigned as incident commander for this incident.",
        channel="channel_id",
    )
    client.chat_postMessage.assert_any_call(
        text="<@new_ol> has been assigned as operations lead for this incident.",
        channel="channel_id",
    )
    # Verify we set the channel purpose with appended roles (including leading newline)
    expected_purpose = (
        "Current channel purpose with no roles. \nIC: <@new_ic> / OL: <@new_ol>"
    )
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id", purpose=expected_purpose
    )


@patch("modules.incident.incident_roles.google_drive.add_metadata")
def test_save_incident_roles_replace_purpose(add_metadata_mock):
    """If the channel purpose already HAS existing IC/OL roles,
    it should replace them with the new roles."""
    client = MagicMock()
    ack = MagicMock()
    # Purpose already has "IC: <@some_ic> / OL: <@some_ol>" that we want to replace
    client.conversations_info.return_value = {
        "channel": {
            "purpose": {
                "value": "Some text here. IC: <@some_ic> / OL: <@some_ol> More text."
            }
        }
    }

    view = {
        "private_metadata": json.dumps(
            {
                "ic_id": "old_ic",
                "ol_id": "old_ol",
                "id": "file_id",
                "channel_id": "channel_id",
            }
        ),
        "state": {
            "values": {
                "ic_name": {"ic_select": {"selected_user": "new_ic"}},
                "ol_name": {"ol_select": {"selected_user": "new_ol"}},
            }
        },
    }

    incident_helper.save_incident_roles(client, ack, view)

    # Verify we ack the request
    ack.assert_called_once()
    # add_metadata is called for both IC and OL
    add_metadata_mock.assert_any_call("file_id", "ic_id", "new_ic")
    add_metadata_mock.assert_any_call("file_id", "ol_id", "new_ol")

    # Verify chat_postMessage was called for both role changes
    client.chat_postMessage.assert_any_call(
        text="<@new_ic> has been assigned as incident commander for this incident.",
        channel="channel_id",
    )
    client.chat_postMessage.assert_any_call(
        text="<@new_ol> has been assigned as operations lead for this incident.",
        channel="channel_id",
    )
    # The existing text "IC: <@some_ic> / OL: <@some_ol>" should be replaced
    expected_purpose = "Some text here. \nIC: <@new_ic> / OL: <@new_ol> More text."
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id", purpose=expected_purpose
    )


@patch("modules.incident.incident_roles.google_drive.add_metadata")
def test_save_incident_roles_purpose_truncation(add_metadata_mock):
    """If the updated purpose exceeds 250 characters, it should be truncated."""
    client = MagicMock()
    ack = MagicMock()

    # Create a long purpose that will exceed 250 characters once we append/replace
    long_description = "X" * 240  # 240 chars
    client.conversations_info.return_value = {
        "channel": {"purpose": {"value": long_description}}
    }

    view = {
        "private_metadata": json.dumps(
            {
                "ic_id": "old_ic",
                "ol_id": "old_ol",
                "id": "file_id",
                "channel_id": "channel_id",
            }
        ),
        "state": {
            "values": {
                "ic_name": {"ic_select": {"selected_user": "very_long_new_ic"}},
                "ol_name": {"ol_select": {"selected_user": "very_long_new_ol"}},
            }
        },
    }

    incident_helper.save_incident_roles(client, ack, view)

    # Verify ack and metadata calls
    ack.assert_called_once()
    add_metadata_mock.assert_any_call("file_id", "ic_id", "very_long_new_ic")
    add_metadata_mock.assert_any_call("file_id", "ol_id", "very_long_new_ol")

    # Verify purpose is truncated. The appended roles add ~31 chars:
    #   " \nIC: <@very_long_new_ic> / OL: <@very_long_new_ol>"
    # If the final is over 250, it should be truncated to 250
    args, kwargs = client.conversations_setPurpose.call_args
    final_purpose = kwargs["purpose"]
    assert (
        len(final_purpose) <= 250
    ), "The purpose should be truncated to 250 characters."

    # Just to illustrate, you could also check that the final purpose starts with the original text:
    assert final_purpose.startswith(
        long_description
    ), "Purpose should contain the start of the original description."
    # and ends somewhere in the appended text. We don't enforce the exact boundary here, just that it's truncated.
