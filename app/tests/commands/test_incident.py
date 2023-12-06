import datetime

from commands import incident

from unittest.mock import call, MagicMock, patch

DATE = datetime.datetime.now().strftime("%Y-%m-%d")


@patch("commands.incident.open_modal")
@patch("commands.incident.log_to_sentinel")
def test_handle_incident_action_buttons_call_incident(
    _log_to_sentinel_mock, open_modal_mock
):
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
@patch("commands.incident.log_to_sentinel")
def test_handle_incident_action_buttons_ignore(
    _log_to_sentinel_mock, increment_acknowledged_count_mock
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
@patch("commands.incident.log_to_sentinel")
def test_handle_incident_action_buttons_ignore_drop_richtext_block(
    _log_to_sentinel_mock,
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
@patch("commands.incident.log_to_sentinel")
def test_handle_incident_action_buttons_ignore_drop_richtext_block_no_type(
    _log_to_sentinel_mock,
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


# Test that the order of the ignore buttons are appended properly and the preview is moved up once the ignore button is clicked


@patch("commands.incident.webhooks.increment_acknowledged_count")
@patch("commands.incident.log_to_sentinel")
def test_handle_incident_action_buttons_link_preview(
    _log_to_sentinel_mock, increment_acknowledged_count_mock
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
                },
                {
                    "text": "test",
                    "title": "title",
                    "app_unfurl_url": "http://blah.com",
                    "thumb_url": "http://blah.com/g/200/200",
                    "image_url": "http://blah.com/g/200/200",
                },
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
                    "text": "test",
                    "title": "title",
                    "app_unfurl_url": "http://blah.com",
                    "thumb_url": "http://blah.com/g/200/200",
                    "image_url": "http://blah.com/g/200/200",
                },
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                },
            ],
        },
    )


@patch("commands.incident.google_drive.list_folders")
def test_incident_open_modal_calls_ack(mock_list_folders):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_modal(client, ack, command, body)
    args = client.views_open.call_args_list
    _, kwargs = args[0]
    ack.assert_called_once()

    assert kwargs["trigger_id"] == "trigger_id"
    assert kwargs["view"]["type"] == "modal"
    assert kwargs["view"]["callback_id"] == "incident_view"
    assert (
        kwargs["view"]["blocks"][6]["element"]["initial_value"]
        == "incident description"
    )
    assert kwargs["view"]["blocks"][7]["element"]["options"][0]["value"] == "id"
    assert (
        kwargs["view"]["blocks"][7]["element"]["options"][0]["text"]["text"] == "name"
    )


@patch("commands.incident.generate_incident_modal_view")
@patch("commands.incident.google_drive.list_folders")
def test_incident_open_modal_calls_generate_incident_modal_view(
    mock_list_folders, mock_generate_incident_modal_view
):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_generate_incident_modal_view.assert_called_once()


@patch("commands.incident.generate_incident_modal_view")
@patch("commands.incident.google_drive.list_folders")
def test_incident_slash_command_calls_generate_incident_modal_view(
    mock_list_folders, mock_generate_incident_modal_view
):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user_id": "user_id"}
    incident.open_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_generate_incident_modal_view.assert_called_once()


@patch("commands.incident.google_drive.list_folders")
def test_incident_open_modal_calls_with_client_locale(mock_list_folders):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_modal(client, ack, command, body)
    args = client.views_open.call_args_list
    _, kwargs = args[0]
    ack.assert_called_once()

    locale = next(
        (block for block in kwargs["view"]["blocks"] if block["block_id"] == "locale"),
        None,
    )["elements"][0]["value"]

    assert locale == "en-US"


@patch("commands.incident.i18n")
@patch("commands.incident.google_drive.list_folders")
def test_incident_open_modal_displays_localized_strings(mock_list_folders, mock_i18n):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_modal(client, ack, command, body)
    args = client.views_open.call_args_list
    _, kwargs = args[0]
    ack.assert_called_once()
    mock_i18n.t.assert_called()


@patch("commands.incident.i18n")
@patch("commands.utils.get_user_locale")
@patch("commands.incident.google_drive.list_folders")
def test_incident_locale_button_calls_ack(
    mock_list_folders, mock_get_user_locale, mock_i18n
):
    ack = MagicMock()
    client = MagicMock()
    command = {"text": "incident_command"}

    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
        "actions": [{"value": "fr-FR"}],
        "view": helper_generate_view(name=command["text"]),
    }
    incident.handle_change_locale_button(ack, client, body)

    ack.assert_called_once()


@patch("commands.incident.generate_incident_modal_view")
@patch("commands.incident.google_drive.list_folders")
def test_incident_locale_button_updates_view_modal_locale_value(
    mock_list_folders,
    mock_generate_incident_modal_view,
):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    ack = MagicMock()
    client = MagicMock()
    options = helper_options()
    command = {"text": "command_name"}
    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
        "actions": [{"value": "fr-FR"}],
        "view": helper_generate_view("command_name"),
    }
    incident.handle_change_locale_button(ack, client, body)

    ack.assert_called
    mock_generate_incident_modal_view.assert_called_with(command, options, "en-US")


@patch("commands.incident.google_drive.list_folders")
def test_incident_local_button_calls_views_update(mock_list_folders):
    mock_list_folders.return_value = [{"id": "id", "name": "name"}]
    ack = MagicMock()
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
        "actions": [{"value": "fr-FR"}],
        "view": helper_generate_view(),
    }
    incident.handle_change_locale_button(ack, client, body)
    args = client.views_update.call_args_list
    _, kwargs = args[0]
    ack.assert_called()
    assert kwargs["view"]["blocks"][0]["elements"][0]["value"] == "en-US"


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_calls_ack(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_called()


@patch("commands.incident.generate_success_modal")
@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_calls_ack_with_response_action(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
    _mock_generate_success_modal,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_called_once_with(
        response_action="update",
        view=_mock_generate_success_modal(body),
    )


def test_incident_submit_returns_error_if_description_is_not_alphanumeric():
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
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
    view = helper_generate_view("a" * 61)
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_any_call(
        response_action="errors",
        errors={
            "name": "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
        },
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_creates_channel_sets_topic_and_announces_channel(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
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
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_adds_creator_to_channel(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "view": view}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    client.users_lookupByEmail.return_value = {"ok": False, "error": "users_not_found"}
    incident.submit(ack, view, say, body, client, logger)
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users='"SLACK_SECURITY_USER_GROUP_ID"'),
        ]
    )


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_truncates_meet_link_if_too_long(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    name = "a" * 60
    view = helper_generate_view(name)
    meet_link = f"https://g.co/meet/incident-{DATE}-{name}"[:78]
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": f"channel_{name}"}
    }
    incident.submit(ack, view, say, body, client, logger)

    ack.assert_called()
    client.bookmarks_add.assert_any_call(
        channel_id="channel_id",
        title="Meet link",
        type="link",
        link=meet_link,
    )

    args = client.bookmarks_add.call_args_list
    _, kwargs = args[0]

    assert len(kwargs["link"]) <= 78


@patch("commands.incident.google_drive.update_incident_list")
@patch("commands.incident.google_drive.merge_data")
@patch("commands.incident.google_drive.create_new_incident")
@patch("commands.incident.google_drive.list_metadata")
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_adds_bookmarks_for_a_meet_and_announces_it(
    _log_to_sentinel_mock,
    _mock_list_metadata,
    _mock_create_new_incident,
    _mock_merge_data,
    _mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
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
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_creates_a_document_and_announces_it(
    _log_to_sentinel_mock,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_update_incident_list,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()

    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
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
@patch("commands.incident.log_to_sentinel")
def test_incident_submit_pulls_oncall_people_into_the_channel(
    _log_to_sentinel_mock,
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
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "on_call_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users="on_call_user_id"),
            call(channel="channel_id", users='"SLACK_SECURITY_USER_GROUP_ID"'),
        ]
    )


def helper_options():
    return [{"text": {"type": "plain_text", "text": "name"}, "value": "id"}]


def helper_client_locale(locale=""):
    if locale == "fr":
        return {
            "ok": True,
            "user": {"id": "user_id", "locale": "fr-FR"},
        }
    else:
        return {
            "ok": True,
            "user": {"id": "user_id", "locale": "en-US"},
        }


def helper_generate_success_modal(channel_url="channel_url", locale="en-US"):
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "incident_modal"},
        "close": {"type": "plain_text", "text": "OK"},
        "blocks": [
            {
                "type": "actions",
                "block_id": "locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "button",
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "incident_change_locale",
                    }
                ],
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Incident successfully created",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": "You have kicked off an incident process.\n\nYou can now use link below to join the discussion:",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{channel_url}|this is a link>",
                },
            },
        ],
    }


def helper_generate_view(name="name", locale="en-US"):
    return {
        "id": "view_id",
        "blocks": [
            {
                "elements": [{"value": locale}],
            },
        ],
        "state": {
            "values": {
                "name": {"name": {"value": name}},
                "locale": {"value": locale},
                "product": {
                    "product": {
                        "selected_option": {
                            "text": {"text": "product"},
                            "value": "folder",
                        }
                    }
                },
            }
        },
    }
