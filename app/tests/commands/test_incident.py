import datetime

from commands import incident

from unittest.mock import MagicMock, patch

DATE = datetime.datetime.now().strftime("%Y-%m-%d")


@patch("commands.incident.open_modal")
def test_handle_incident_action_buttons_call_incident(open_modal_mock):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "call-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "user": {"id": "user_id"},
    }
    incident.handle_incident_action_buttons(client, ack, body, logger)
    open_modal_mock.assert_called_with(client, ack, {"text": "incident_id"}, body)


@patch("commands.incident.webhooks.increment_acknowledged_count")
def test_handle_incident_action_buttons_ignore(increment_acknowledged_count_mock):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
        },
    }
    incident.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
        },
    )


@patch("commands.incident.webhooks.increment_acknowledged_count")
def test_handle_incident_action_buttons_ignore_drop_richtext_block(
    increment_acknowledged_count_mock,
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    }
    incident.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
            "blocks": [],
        },
    )


@patch("commands.incident.webhooks.increment_acknowledged_count")
def test_handle_incident_action_buttons_ignore_drop_richtext_block_no_type(
    increment_acknowledged_count_mock,
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
            "blocks": [
                {
                    "foo": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    }
    incident.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
            "blocks": [
                {
                    "foo": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    )


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
@patch("commands.incident.google_drive.list_metadata")
def test_incident_submit_calls_ack(
    _mock_list_metadata,
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
        errors={
            "name": "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
        },
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
        errors={
            "name": "Description must be less than 80 characters // La description doit contenir moins de 80 caractères"
        },
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
def test_incident_submit_creates_channel_sets_topic_and_announces_channel(
    _mock_list_metadata,
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
        text="<@user_id> has kicked off a new incident: name for product in <#channel_id>\n<@user_id> a initié un nouvel incident: name pour product dans <#channel_id>",
        channel=incident.INCIDENT_CHANNEL,
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
def test_incident_submit_adds_bookmarks_for_a_meet_and_announces_it(
    _mock_list_metadata,
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
@patch("commands.incident.google_drive.list_metadata")
def test_incident_submit_creates_a_document_and_announces_it(
    mock_list_metadata,
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

    mock_list_metadata.return_value = {"appProperties": {}}

    incident.submit(ack, view, say, body, client, logger)
    mock_create_new_incident.assert_called_once_with(f"{DATE}-name", "folder")
    mock_merge_data.assert_called_once_with(
        "id", "name", "product", "https://gcdigital.slack.com/archives/channel_id", ""
    )
    mock_update_incident_list.assert_called_once_with(
        "https://docs.google.com/document/d/id/edit",
        "name",
        f"{DATE}-name",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.opsgenie.get_on_call_users")
def test_incident_submit_pulls_oncall_people_into_the_channel(
    mock_get_on_call_users,
    mock_list_metadata,
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
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {"id": "user_id", "profile": {"display_name_normalized": "name"}},
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.conversations_invite.assert_called_once_with(
        channel="channel_id", users="user_id"
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
