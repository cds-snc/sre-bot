import datetime

from commands import incident

from unittest.mock import MagicMock, patch

DATE = datetime.datetime.now().strftime("%Y-%m-%d")


@patch("commands.incident.google_drive.list_folders")
def test_incident_open_modal_calls_ack(mock_list_folders):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id"}
    incident.open_modal(client, ack, command, body)
    args = client.views_open.call_args_list
    _, kwargs = args[0]
    ack.assert_called_once()
    assert kwargs["trigger_id"] == "trigger_id"
    assert kwargs["view"]["type"] == "modal"
    assert kwargs["view"]["callback_id"] == "incident_view"
    assert (
        kwargs["view"]["blocks"][5]["element"]["initial_value"]
        == "incident description"
    )
    assert kwargs["view"]["blocks"][6]["element"]["options"][0]["value"] == "id"
    assert (
        kwargs["view"]["blocks"][6]["element"]["options"][0]["text"]["text"] == "name"
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
def test_incident_submit_calls_ack(
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_called_once()


def test_incident_submit_returns_error_if_description_is_not_alphanumeric():
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_any_call(
        response_action="errors",
        errors={"name": "Description must only contain number and letters"},
    )


def test_incident_submit_returns_error_if_description_is_too_long():
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view("a" * 81)
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_any_call(
        response_action="errors",
        errors={"name": "Description must be less than 80 characters"},
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
def test_incident_submit_creates_channel_sets_topic_and_announces_channel(
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    incident.submit(ack, view, say, body, client, logger)
    client.conversations_create.assert_called_once_with(name=f"incident-{DATE}-name")
    client.conversations_setTopic.assert_called_once_with(
        channel="channel_id", topic="Incident: name / product"
    )
    say.assert_any_call(
        text="<@user_id> has kicked off a new incident: name for product in <#channel_id>",
        channel=incident.INCIDENT_CHANNEL,
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
def test_incident_submit_adds_bookmarks_for_a_meet_and_announces_it(
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    incident.submit(ack, view, say, body, client, logger)

    client.bookmarks_add.assert_any_call(
        channel_id="channel_id",
        title="Meet link",
        type="link",
        link=f"https://g.co/meet/incident-{DATE}-name",
    )

    say.assert_any_call(
        text=f"A hangout has been created at: https://g.co/meet/incident-{DATE}-name",
        channel="channel_id",
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
def test_incident_submit_creates_a_document_and_announces_it(
    mock_create_new_incident,
    mock_merge_data,
    mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }

    mock_create_new_incident.return_value = "id"

    incident.submit(ack, view, say, body, client, logger)
    mock_create_new_incident.assert_called_once_with(f"{DATE}-name", "folder")
    mock_merge_data.assert_called_once_with(
        "id", "name", "product", "https://gcdigital.slack.com/archives/channel_id"
    )
    mock_update_incident_list.assert_called_once_with(
        "https://docs.google.com/document/d/id/edit",
        "name",
        f"{DATE}-name",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
    )


def helper_generate_view(name="name"):
    return {
        "state": {
            "values": {
                "name": {"name": {"value": name}},
                "product": {
                    "product": {
                        "selected_option": {
                            "text": {"text": "product"},
                            "value": "folder",
                        }
                    }
                },
            }
        }
    }
