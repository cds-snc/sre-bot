from commands import role

from unittest.mock import ANY, MagicMock, patch

help_text_fr = "\n `/role help` - For help in English\n---\n\n `/role aide`\n       - afficher les informations d'utilisation et le texte d'aide \n `/role nouveau`\n       - créer un nouveau rôle"
help_text_en = "\n `/role aide` - Pour de l'aide en français\n---\n\n `/role help`\n       - show usage information and help text\n `/role new`\n       - create a new role\n"


def test_role_command_handles_empty_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    role.role_command(
        ack,
        {"text": "", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_en)


def test_role_command_handles_empty_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")

    role.role_command(
        ack,
        {"text": "", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_fr)


def test_role_command_handles_help_EN_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    role.role_command(
        ack,
        {"text": "help", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_en)


def test_role_command_handles_help_EN_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    role.role_command(
        ack,
        {"text": "help", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_en)


def test_role_command_handles_help_FR_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    role.role_command(
        ack,
        {"text": "aide", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_fr)


def test_role_command_handles_unknown_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    role.role_command(
        ack,
        {"text": "foo", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(
        "Sorry but I don't understand this command. Please type /role help to get usage information"
    )


def test_role_command_handles_unknown_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")
    role.role_command(
        ack,
        {"text": "foo", "command": "/role"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(
        "Désolé mais je ne comprends pas cette commande. Veuillez saisir /aide help pour obtenir des informations sur l'utilisation"
    )


@patch("commands.role.request_start_modal")
def test_role_command_handles_new_role_EN_command(request_start_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    role.role_command(ack, {"text": "new"}, MagicMock(), respond, client, body)
    ack.assert_called
    request_start_modal.assert_called_with(client, body, locale="en-US")


@patch("commands.role.request_start_modal")
def test_role_command_handles_new_role_FR_command(request_start_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    role.role_command(ack, {"text": "nouveau"}, MagicMock(), respond, client, body)
    ack.assert_called
    request_start_modal.assert_called_with(client, body, locale="fr-FR")


@patch("commands.role.role_modal_view")
def test_role_action_update_locale_to_FR(role_modal_view):
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")

    role.update_modal_locale(ack, client, body)
    ack.assert_called
    role_modal_view.assert_called_with("fr-FR")


@patch("commands.role.role_modal_view")
def test_role_action_update_locale_to_EN(role_modal_view):
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR")

    role.update_modal_locale(ack, client, body)
    ack.assert_called
    role_modal_view.assert_called_with("en-US")


def test_request_start_modal():
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "view": {"state": {"values": {}}},
        "user_id": "user_id",
    }
    role.request_start_modal(client, body, "en-US")
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


def test_update_modal_locale_to_EN():
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR")

    role.update_modal_locale(ack, client, body)
    args = client.views_update.call_args_list
    _, kwargs = args[0]
    ack.assert_called()
    assert kwargs["view"]["blocks"][0]["elements"][0]["value"] == "en-US"


def test_update_modal_locale_to_FR():
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")

    role.update_modal_locale(ack, client, body)
    args = client.views_update.call_args_list
    _, kwargs = args[0]
    ack.assert_called()
    assert kwargs["view"]["blocks"][0]["elements"][0]["value"] == "fr-FR"


# @patch("commands.role.google_drive.create_new_folder")
# def test_create_new_folder(mock_create_new_folder):
#     ack = MagicMock()
#     say = MagicMock()
#     logger = MagicMock()
#     body = body = helper_body_payload("en-US")
#     client = MagicMock()
#     mock_parent_folder = MagicMock()
#     mock_create_new_folder.return_value = "id"
#     role.role_view_handler(ack, body, say, logger, client)
#     mock_create_new_folder.assert_called_once_with("name", mock_parent_folder)


def helper_client_locale(locale=""):
    if locale == "fr":
        return {
            "ok": True,
            "user": {"id": "U00AAAAAAA0", "locale": "fr-FR"},
        }
    else:
        return {
            "ok": True,
            "user": {"id": "U00AAAAAAA0", "locale": "en-US"},
        }


def helper_body_payload(locale):
    return {
        "user": {"id": "user_id"},
        "view": {
            "id": "view_id",
            "state": {"values": {"role_name": {"role_name": {"value": "foo"}}}},
        },
        "actions": [{"action_id": "role_change_locale", "value": locale}],
    }
