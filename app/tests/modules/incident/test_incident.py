import datetime
from unittest.mock import ANY, MagicMock, patch
from modules import incident

DATE = datetime.datetime.now().strftime("%Y-%m-%d")


@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.i18n")
@patch("modules.incident.incident.slack_users.get_user_locale")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_calls_ack(
    mock_list_incident_folders,
    mock_get_user_locale,
    mock_i18n,
    mock_generate_incident_modal_view,
):
    loaded_view = mock_generate_incident_modal_view.return_value = ANY
    mock_i18n.t.side_effect = [
        "SRE - Start an incident",
        "Launching incident process...",
    ]
    mock_get_user_locale.return_value = "en-US"
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_create_incident_modal(client, ack, command, body)
    args = client.views_open.call_args_list
    _, kwargs = args[0]
    ack.assert_called_once()

    assert kwargs["trigger_id"] == "trigger_id"
    assert kwargs["view"]["type"] == "modal"
    assert kwargs["view"]["callback_id"] == "incident_view"
    assert kwargs["view"]["title"]["text"] == "SRE - Start an incident"
    assert (
        kwargs["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: Launching incident process..."
    )
    mock_generate_incident_modal_view.assert_called_once_with(
        command, ANY, None, "en-US"
    )
    client.views_update.assert_called_once_with(view_id=ANY, view=loaded_view)


@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_calls_generate_incident_modal_view(
    mock_list_incident_folders, mock_generate_incident_modal_view
):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_create_incident_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_generate_incident_modal_view.assert_called_once()


@patch("modules.incident.incident.i18n.set")
@patch("modules.incident.incident.slack_users.get_user_locale")
@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_calls_i18n_set(
    mock_list_incident_folders,
    mock_generate_incident_modal_view,
    mock_get_user_locale,
    mock_i18n_set,
):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    mock_get_user_locale.return_value = "en-US"
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user_id": "user_id"}
    incident.open_create_incident_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_generate_incident_modal_view.assert_called_once()
    mock_i18n_set.assert_called_once_with("locale", "en-US")


@patch("modules.incident.incident.i18n")
@patch("modules.incident.incident.slack_users.get_user_locale")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
@patch("modules.incident.incident.generate_incident_modal_view")
def test_incident_open_modal_calls_get_user_locale(
    mock_generate_incident_modal_view,
    mock_list_incident_folders,
    mock_get_user_locale,
    mock_i18n,
):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    mock_get_user_locale.return_value = "fr-FR"
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_create_incident_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_get_user_locale.assert_called_once_with(client, "user_id")
    mock_generate_incident_modal_view.assert_called_once_with(
        command, ANY, None, "fr-FR"
    )


@patch("modules.incident.incident.i18n")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_displays_localized_strings(
    mock_list_incident_folders, mock_i18n
):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    ack = MagicMock()
    command = {"text": "incident description"}
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}
    incident.open_create_incident_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_i18n.t.assert_called()


@patch("modules.incident.incident.i18n")
@patch("integrations.slack.users.get_user_locale")
@patch("modules.incident.incident.incident_folder")
def test_incident_locale_button_calls_ack(
    mock_incident_folder, mock_get_user_locale, mock_i18n
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


@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_locale_button_updates_view_modal_locale_value(
    mock_list_incident_folders,
    mock_generate_incident_modal_view,
):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
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

    ack.assert_called()
    mock_generate_incident_modal_view.assert_called_with(
        command, options, None, "en-US"
    )


@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_local_button_calls_views_update(mock_list_incident_folders):
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
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


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_calls_succeeds(
    mock_create_incident_conversation,
    mock_logger,
    mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    incident.submit(ack, view, say, body, client)
    ack.assert_called()


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_calls_views_open(
    mock_create_incident_conversation,
    mock_logger,
    mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    incident.submit(ack, view, say, body, client)
    ack.assert_called_once()
    client.views_open.assert_called_once()


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_returns_error_if_description_is_not_alphanumeric(
    mock_create_incident_conversation,
    mock_logger,
    mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    incident.submit(ack, view, say, body, client)
    ack.assert_any_call(
        response_action="errors",
        errors={
            "name": "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
        },
    )


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_returns_error_if_description_is_too_long(
    mock_create_incident_conversation,
    mock_logger,
    mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()

    view = helper_generate_view("a" * 61)
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    incident.submit(ack, view, say, body, client)
    ack.assert_any_call(
        response_action="errors",
        errors={
            "name": "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
        },
    )


def helper_options():
    return [{"text": {"type": "plain_text", "text": "name"}, "value": "id"}]


def helper_client_locale(locale="en-US"):
    return {
        "ok": True,
        "user": {"id": "user_id", "locale": locale},
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
                "security_incident": {
                    "security_incident": {
                        "selected_option": {
                            "text": {"text": "yes"},
                            "value": "yes",
                        }
                    }
                },
            }
        },
    }
