from modules import secret

from unittest.mock import MagicMock, patch


@patch("modules.secret.secret.generate_secret_command_modal_view")
@patch("modules.secret.secret.slack_users.get_user_locale")
def test_secret_command(mock_get_user_locale, mock_generate_secret_command_modal_view):
    client = MagicMock()
    ack = MagicMock()

    mock_get_user_locale.return_value = "en-US"

    command = "secret"

    body = {
        "trigger_id": "trigger_id",
        "user": {"id": "user_id"},
    }

    secret.secret_command(client, ack, command, body)

    mock_get_user_locale.assert_called_once_with(client, "user_id")
    mock_generate_secret_command_modal_view.assert_called_once_with(
        command, "user_id", "en-US"
    )

    client.views_open.assert_called_once_with(
        trigger_id="trigger_id",
        view=mock_generate_secret_command_modal_view.return_value,
    )


@patch("modules.secret.secret.requests")
@patch("modules.secret.secret.time")
def test_secret_view_handler_with_succesfull_request(mock_time, mock_requests):
    ack = MagicMock()
    client = MagicMock()
    logger = MagicMock()
    view = {
        "blocks": [
            {
                "elements": [
                    {
                        "value": "en-US",
                    }
                ]
            }
        ],
        "state": {
            "values": {
                "secret_input": {
                    "secret_submission": {
                        "value": "secret",
                    }
                },
                "product": {
                    "secret_ttl": {
                        "selected_option": {
                            "value": "1",
                        }
                    }
                },
            }
        },
        "private_metadata": "private_metadata",
    }

    mock_time.time.return_value = 0

    mock_requests.post.return_value.json.return_value = {"id": "id"}

    secret.secret_view_handler(ack, client, view, logger)

    ack.assert_called_once_with()

    mock_time.time.assert_called_once_with()
    mock_requests.post.assert_called_once_with(
        "https://encrypted-message.cdssandbox.xyz/encrypt",
        json={"body": "secret", "ttl": 1},
        timeout=10,
        headers={"Content-Type": "application/json"},
    )

    client.chat_postEphemeral.assert_called_once_with(
        channel="private_metadata",
        user="private_metadata",
        text="Your secret is available at the following link: https://encrypted-message.cdssandbox.xyz/en/view/id",
    )


@patch("modules.secret.secret.requests")
@patch("modules.secret.secret.time")
def test_secret_view_handler_with_failed_request(mock_time, mock_requests):
    ack = MagicMock()
    client = MagicMock()
    logger = MagicMock()
    view = {
        "blocks": [
            {
                "elements": [
                    {
                        "value": "en-US",
                    }
                ]
            }
        ],
        "state": {
            "values": {
                "secret_input": {
                    "secret_submission": {
                        "value": "secret",
                    }
                },
                "product": {
                    "secret_ttl": {
                        "selected_option": {
                            "value": "1",
                        }
                    }
                },
            }
        },
        "private_metadata": "private_metadata",
    }

    mock_time.time.return_value = 0

    mock_requests.post.return_value.json.return_value = {}

    secret.secret_view_handler(ack, client, view, logger)

    ack.assert_called_once_with()

    mock_time.time.assert_called_once_with()
    mock_requests.post.assert_called_once_with(
        "https://encrypted-message.cdssandbox.xyz/encrypt",
        json={"body": "secret", "ttl": 1},
        timeout=10,
        headers={"Content-Type": "application/json"},
    )

    client.chat_postEphemeral.assert_called_once_with(
        channel="private_metadata",
        user="private_metadata",
        text="There was an error creating your secret",
    )


@patch("modules.secret.secret.generate_secret_command_modal_view")
def test_handle_change_locale_button(mock_generate_secret_command_modal_view):
    ack = MagicMock()
    client = MagicMock()
    body = {
        "actions": [
            {
                "value": "en-US",
            }
        ],
        "user": {"id": "user_id"},
        "view": {
            "id": "view_id",
            "state": {
                "values": {
                    "secret_input": {
                        "secret_submission": {
                            "value": "secret",
                        }
                    }
                }
            },
        },
    }

    secret.handle_change_locale_button(ack, client, body)

    ack.assert_called_once_with()

    mock_generate_secret_command_modal_view.assert_called_once_with(
        {"text": "secret"},
        "user_id",
        "fr-FR",
    )

    client.views_update.assert_called_once_with(
        view_id="view_id",
        view=mock_generate_secret_command_modal_view.return_value,
    )


def test_generate_secret_command_modal_view():
    command = {"text": "secret"}
    user_id = "user_id"
    locale = "fr-FR"

    view = secret.generate_secret_command_modal_view(command, user_id, locale)
    assert view == {
        "type": "modal",
        "private_metadata": "user_id",
        "callback_id": "secret_view",
        "title": {"type": "plain_text", "text": "Partager secret"},
        "submit": {"type": "plain_text", "text": "Soumettre"},
        "blocks": [
            {
                "type": "actions",
                "block_id": "locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "English",
                            "emoji": True,
                        },
                        "value": "fr-FR",
                        "action_id": "secret_change_locale",
                    }
                ],
            },
            {
                "type": "input",
                "block_id": "secret_input",
                "label": {"type": "plain_text", "text": "Secret"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "secret_submission",
                    "initial_value": "secret",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Entrez votre secret ici",
                    },
                },
            },
            {
                "block_id": "product",
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Durée de vie"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "7 jours"},
                            "value": "604800",
                        },
                        {
                            "text": {"type": "plain_text", "text": "3 jours"},
                            "value": "259200",
                        },
                        {
                            "text": {"type": "plain_text", "text": "1 jour"},
                            "value": "86400",
                        },
                        {
                            "text": {"type": "plain_text", "text": "12 heures"},
                            "value": "43200",
                        },
                        {
                            "text": {"type": "plain_text", "text": "4 heures"},
                            "value": "14400",
                        },
                        {
                            "text": {"type": "plain_text", "text": "1 heure"},
                            "value": "3600",
                        },
                        {
                            "text": {"type": "plain_text", "text": "30 minutes"},
                            "value": "1800",
                        },
                        {
                            "text": {"type": "plain_text", "text": "5 minutes"},
                            "value": "300",
                        },
                    ],
                    "action_id": "secret_ttl",
                },
                "label": {"type": "plain_text", "text": "Durée de vie", "emoji": True},
            },
        ],
    }
