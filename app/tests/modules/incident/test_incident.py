import datetime
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import i18n
import pytest
from pydantic import ValidationError
from slack_sdk.errors import SlackApiError

from models.incidents import IncidentPayload
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
    assert kwargs["view"]["blocks"][0]["text"]["text"] == ":beach-ball: Launching incident process..."
    mock_generate_incident_modal_view.assert_called_once_with(command, ANY, None, "en-US")
    client.views_update.assert_called_once_with(view_id=ANY, view=loaded_view)


@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.slack_users.get_user_locale")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_passes_source_private_metadata(
    mock_list_incident_folders,
    mock_get_user_locale,
    mock_generate_incident_modal_view,
):
    mock_get_user_locale.return_value = "en-US"
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
    client = MagicMock()
    ack = MagicMock()
    command = {
        "text": "incident description",
        "private_metadata": {
            "source_channel_id": "channel_id",
            "source_message_ts": "123.456",
        },
    }
    body = {"trigger_id": "trigger_id", "user": {"id": "user_id"}}

    incident.open_create_incident_modal(client, ack, command, body)

    mock_generate_incident_modal_view.assert_called_once_with(
        command,
        ANY,
        json.dumps(
            {
                "source_channel_id": "channel_id",
                "source_message_ts": "123.456",
            }
        ),
        "en-US",
    )


@patch("modules.incident.incident.generate_incident_modal_view")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_calls_generate_incident_modal_view(mock_list_incident_folders, mock_generate_incident_modal_view):
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
    mock_generate_incident_modal_view.assert_called_once_with(command, ANY, None, "fr-FR")


@patch("modules.incident.incident.i18n")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_open_modal_displays_localized_strings(mock_list_incident_folders, mock_i18n):
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
def test_incident_locale_button_calls_ack(mock_incident_folder, mock_get_user_locale, mock_i18n):
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
        "view": helper_generate_view("command_name", private_metadata='{"source_channel_id": "channel"}'),
    }
    incident.handle_change_locale_button(ack, client, body)

    ack.assert_called()
    mock_generate_incident_modal_view.assert_called_with(command, options, '{"source_channel_id": "channel"}', "en-US")


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
    incident_payload = IncidentPayload(
        name="name",
        folder="folder",
        product="product",
        security_incident="yes",
        user_id="user_id",
        channel_id="channel_id",
        channel_name="channel_name",
        slug="slug",
        severity="sev-1",
    )
    incident.submit(ack, view, say, body, client)
    ack.assert_called()
    client.views_open.assert_called_once()
    info_calls = [
        call(
            "incident_channel_created",
            channel_id="channel_id",
            channel_name="channel_name",
            slug="slug",
        ),
        call(
            "incident_modal_submitted",
            name="name",
            name_length=len("name"),
            folder="folder",
            product="product",
            security_incident="yes",
            body=body,
        ),
    ]
    mock_logger.info.assert_has_calls(info_calls)
    mock_log_to_sentinel.assert_called_once_with("incident_called", body)

    mock_core.initiate_resources_creation.assert_called_once_with(
        client=client,
        incident_payload=incident_payload,
    )


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_adds_source_alert_permalink(
    mock_create_incident_conversation,
    _mock_logger,
    _mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view(
        private_metadata=json.dumps(
            {
                "source_channel_id": "source_channel",
                "source_message_ts": "123.456",
            }
        )
    )
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/source"}
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    incident.submit(ack, view, say, body, client)

    client.chat_getPermalink.assert_called_once_with(channel="source_channel", message_ts="123.456")
    mock_core.initiate_resources_creation.assert_called_once_with(
        client=client,
        incident_payload=IncidentPayload(
            name="name",
            folder="folder",
            product="product",
            security_incident="yes",
            user_id="user_id",
            channel_id="channel_id",
            channel_name="channel_name",
            slug="slug",
            severity="sev-1",
            source_alert_permalink="https://slack/source",
        ),
    )


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_ignores_malformed_source_metadata(
    mock_create_incident_conversation,
    mock_logger,
    _mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view(private_metadata="not-json")
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    incident.submit(ack, view, say, body, client)

    client.chat_getPermalink.assert_not_called()
    mock_logger.warning.assert_called_once()
    assert mock_core.initiate_resources_creation.call_args.kwargs["incident_payload"].source_alert_permalink is None


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_continues_when_source_permalink_fails(
    mock_create_incident_conversation,
    mock_logger,
    _mock_log_to_sentinel,
    mock_core,
):
    ack = MagicMock()
    view = helper_generate_view(
        private_metadata=json.dumps(
            {
                "source_channel_id": "source_channel",
                "source_message_ts": "123.456",
            }
        )
    )
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    client.chat_getPermalink.side_effect = Exception("slack error")
    mock_create_incident_conversation.create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    incident.submit(ack, view, say, body, client)

    mock_logger.warning.assert_called_once_with(
        "source_alert_permalink_failed",
        source_channel_id="source_channel",
        source_message_ts="123.456",
        error="slack error",
    )
    assert mock_core.initiate_resources_creation.call_args.kwargs["incident_payload"].source_alert_permalink is None


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_incident_submit_returns_error_if_description_is_not_alphanumeric(
    mock_create_incident_conversation,
    _mock_logger,
    _mock_log_to_sentinel,
    _mock_core,
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
    _mock_logger,
    _mock_log_to_sentinel,
    _mock_core,
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
        errors={"name": "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"},
    )


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_submit_conversation_creation_error(
    mock_create_incident_conversation,
    mock_logger,
    _mock_log_to_sentinel,
    _mock_core,
):
    ack = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.create_incident_conversation.side_effect = SlackApiError(
        message="error", response=MagicMock()
    )
    incident.submit(ack, view, say, body, client)
    ack.assert_called()
    say.assert_called_with(
        text=":warning: Channel creation failed. Please contact the SRE team.",
        channel="user_id",
    )
    mock_logger.error.assert_called_once_with("incident_channel_creation_failed", error=ANY, incident_name="name")


@patch("modules.incident.incident.core")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident.logger")
@patch("modules.incident.incident.incident_conversation")
def test_submit_initiate_resources_creation_error(
    mock_create_incident_conversation,
    mock_logger,
    _mock_log_to_sentinel,
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
    mock_core.initiate_resources_creation.side_effect = Exception("error")
    incident.submit(ack, view, say, body, client)
    ack.assert_called()
    say.assert_called_with(
        text=":warning: There was an error initiating the incident resources. Please contact the SRE team.",
        channel="channel_id",
    )
    mock_logger.error.assert_called_once_with(
        "incident_resources_creation_failed",
        error=ANY,
        incident_name="name",
        channel_id="channel_id",
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


def helper_generate_view(name="name", locale="en-US", private_metadata=""):
    return {
        "id": "view_id",
        "private_metadata": private_metadata,
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
                "severity": {
                    "severity": {
                        "selected_option": {
                            "text": {"text": "sev-1"},
                            "value": "sev-1",
                        }
                    }
                },
            }
        },
    }


# -- policy help: modal, submit and payload ------------------------------------------------------


def _policy_modal(locale: str = "en-US") -> dict[str, Any]:
    previous = i18n.get("locale")
    i18n.set("locale", locale)
    try:
        with patch(
            "modules.incident.incident.get_incident_response_settings", return_value=SimpleNamespace(handbook_id="HANDBOOK")
        ):
            return incident.generate_incident_modal_view({"text": "incident description"}, [], None, locale)
    finally:
        i18n.set("locale", previous)


def _policy_block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def _policy_submitted_view(policy: dict[str, Any] | None = None, *, include_block: bool = True) -> dict[str, Any]:
    view = helper_generate_view()
    view["state"]["values"]["security_incident"] = {"security_incident": {"selected_option": {"value": "no"}}}
    if include_block:
        view["state"]["values"]["policy_help"] = {"policy_help": policy if policy is not None else {"selected_option": None}}
    return view


def _policy_submit(view: dict[str, Any]) -> IncidentPayload:
    """Submit the view and return the payload handed to the resource-creation step."""
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    previous = i18n.get("locale")
    try:
        with (
            patch("modules.incident.incident.core") as core,
            patch("modules.incident.incident.log_to_sentinel"),
            patch("modules.incident.incident.logger"),
            patch("modules.incident.incident.incident_conversation") as conversation,
        ):
            conversation.create_incident_conversation.return_value = {
                "channel_id": "channel_id",
                "channel_name": "channel_name",
                "slug": "slug",
            }
            incident.submit(MagicMock(), view, MagicMock(), body, MagicMock())
    finally:
        i18n.set("locale", previous)
    payload: IncidentPayload = core.initiate_resources_creation.call_args.kwargs["incident_payload"]
    return payload


def test_the_modal_asks_the_policy_question_in_english():
    block = _policy_block(_policy_modal("en-US"), "policy_help")

    assert block["label"]["text"] == "Do you need policy help?"
    assert block["hint"]["text"] == (
        "e.g., the incident may involve privacy, personal information, terms of use violations, etc."
    )


def test_the_modal_asks_the_policy_question_in_french():
    block = _policy_block(_policy_modal("fr-FR"), "policy_help")

    assert block["label"]["text"] == "Avez-vous besoin d'aide en matière de politiques?"
    assert "vie privée" in block["hint"]["text"]


def test_the_policy_question_is_a_required_input_block():
    """The submitter must answer, so the stored answer is always an explicit yes or no."""
    block = _policy_block(_policy_modal(), "policy_help")

    assert block["type"] == "input"
    assert not block.get("optional", False)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("en-US", [("Yes", "yes"), ("No", "no")]), ("fr-FR", [("Oui", "yes"), ("Non", "no")])],
)
def test_the_policy_question_offers_localized_yes_and_no_in_that_order(locale, expected):
    element = _policy_block(_policy_modal(locale), "policy_help")["element"]

    assert element["type"] == "static_select"
    assert [(o["text"]["text"], o["value"]) for o in element["options"]] == expected


def test_the_policy_question_has_a_localized_placeholder():
    assert (
        _policy_block(_policy_modal("en-US"), "policy_help")["element"]["placeholder"]["text"] == "Select if you need policy help"
    )
    assert "politiques" in _policy_block(_policy_modal("fr-FR"), "policy_help")["element"]["placeholder"]["text"]


def test_the_policy_block_and_action_ids_match_the_keys_the_submit_reads():
    block = _policy_block(_policy_modal(), "policy_help")

    assert block["block_id"] == "policy_help"
    assert block["element"]["action_id"] == "policy_help"


def test_the_policy_question_follows_the_security_question():
    """The policy question sits directly after the security question, ahead of the handbook link."""
    view = _policy_modal()
    block_ids = [block.get("block_id") for block in view["blocks"]]

    assert block_ids.index("policy_help") == block_ids.index("security_incident") + 1
    assert view["blocks"][-1]["type"] == "context"


def test_the_security_question_is_unchanged():
    block = _policy_block(_policy_modal(), "security_incident")

    assert block["label"]["text"] == "Is this a security incident?"
    assert [o["value"] for o in block["element"]["options"]] == ["yes", "no"]


def test_the_locale_button_is_still_the_first_block():
    """Submit and locale toggling read the locale from the first block, so adding a field must not move it."""
    view = _policy_modal()

    assert view["blocks"][0]["block_id"] == "locale"
    assert view["blocks"][0]["elements"][0]["value"] == "en-US"


def test_every_block_id_in_the_modal_is_unique():
    ids = [block["block_id"] for block in _policy_modal()["blocks"] if "block_id" in block]

    assert len(ids) == len(set(ids))
    assert {"name", "product", "severity", "security_incident", "policy_help"} <= set(ids)


@pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
def test_the_policy_strings_exist_in_both_locales(locale):
    previous = i18n.get("locale")
    i18n.set("locale", locale)
    try:
        for key in ("policy_help", "policy_help_hint", "policy_help_placeholder"):
            translated = i18n.t(f"incident.modal.{key}")
            assert translated and translated != f"incident.modal.{key}"
    finally:
        i18n.set("locale", previous)


def test_the_locale_toggle_rebuilds_the_modal_with_the_policy_question():
    """Switching language re-renders the whole modal, so the policy question stays present in the new locale."""
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
        "actions": [{"value": "en-US"}],
        "view": helper_generate_view(),
    }
    previous = i18n.get("locale")

    try:
        with (
            patch("modules.incident.incident.incident_folder.list_incident_folders", return_value=[{"id": "id", "name": "name"}]),
            patch(
                "modules.incident.incident.get_incident_response_settings", return_value=SimpleNamespace(handbook_id="HANDBOOK")
            ),
        ):
            incident.handle_change_locale_button(MagicMock(), client, body)
    finally:
        i18n.set("locale", previous)

    view = client.views_update.call_args.kwargs["view"]
    assert _policy_block(view, "policy_help")["label"]["text"] == "Avez-vous besoin d'aide en matière de politiques?"


@pytest.mark.parametrize("answer", ["yes", "no"])
def test_submitting_an_answer_passes_it_to_resource_creation(answer):
    payload = _policy_submit(_policy_submitted_view({"selected_option": {"value": answer}}))

    assert payload.policy_help == answer


def test_a_submission_without_the_policy_block_defaults_to_no():
    """A modal opened before the field existed submits no policy block and must still create the incident."""
    payload = _policy_submit(_policy_submitted_view(include_block=False))

    assert payload.policy_help == "no"


def test_a_submission_with_no_selected_option_defaults_to_no():
    payload = _policy_submit(_policy_submitted_view({"selected_option": None}))

    assert payload.policy_help == "no"


@pytest.mark.parametrize("security", ["yes", "no"])
def test_the_policy_answer_is_independent_of_the_security_answer(security):
    view = _policy_submitted_view({"selected_option": {"value": "yes"}})
    view["state"]["values"]["security_incident"] = {"security_incident": {"selected_option": {"value": security}}}

    payload = _policy_submit(view)

    assert (payload.security_incident, payload.policy_help) == (security, "yes")


def test_the_rest_of_the_payload_is_unaffected_by_the_policy_answer():
    payload = _policy_submit(_policy_submitted_view({"selected_option": {"value": "yes"}}))

    assert payload == IncidentPayload(
        name="name",
        folder="folder",
        product="product",
        security_incident="no",
        policy_help="yes",
        user_id="user_id",
        channel_id="channel_id",
        channel_name="channel_name",
        slug="slug",
        severity="sev-1",
    )


def test_an_invalid_name_is_rejected_before_any_resource_is_created():
    view = _policy_submitted_view({"selected_option": {"value": "yes"}})
    view["state"]["values"]["name"] = {"name": {"value": "bad/name!"}}
    ack = MagicMock()

    with (
        patch("modules.incident.incident.core") as core,
        patch("modules.incident.incident.incident_conversation") as conversation,
    ):
        incident.submit(ack, view, MagicMock(), {"user": {"id": "user_id"}, "view": view}, MagicMock())

    assert "name" in ack.call_args.kwargs["errors"]
    conversation.create_incident_conversation.assert_not_called()
    core.initiate_resources_creation.assert_not_called()


def _payload_fields(**overrides):
    return {
        "name": "name",
        "folder": "folder",
        "product": "product",
        "security_incident": "no",
        "user_id": "user_id",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    } | overrides


def test_payload_policy_help_defaults_to_no():
    assert IncidentPayload(**_payload_fields()).policy_help == "no"


@pytest.mark.parametrize("answer", ["yes", "no"])
def test_payload_policy_help_keeps_the_submitted_answer(answer):
    assert IncidentPayload(**_payload_fields(policy_help=answer)).policy_help == answer


def test_payload_policy_help_must_be_a_string():
    with pytest.raises(ValidationError):
        IncidentPayload(**_payload_fields(policy_help=["yes"]))


def test_payload_still_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        IncidentPayload(**_payload_fields(), policy_helper="yes")
