from modules import role

from unittest.mock import ANY, MagicMock, patch, call


ROLE_CONSTANTS = {
    "SCORING_GUIDE_TEMPLATE": "scoring_guide_template",
    "CORE_VALUES_INTERVIEW_NOTES_TEMPLATE": "core_values_template",
    "TECHNICAL_INTERVIEW_NOTES_TEMPLATE": "technical_interview_template",
    "INTAKE_FORM_TEMPLATE": "intake_form_template",
    "PHONE_SCREEN_TEMPLATE": "phone_screen_template",
    "RECRUITMENT_FEEDBACK_TEMPLATE": "recruitment_feedback_template",
    "PANELIST_GUIDEBOOK_TEMPLATE": "panelist_guidebook_template",
    "INTERNAL_TALENT_FOLDER": "mock_internal_talent_folder",
    "TEMPLATES_FOLDER": "mock_templates_folder",
}

help_text_fr = "\n `/role help` - For help in English\n---\n\n `/role aide`\n       - afficher les informations d'utilisation et le texte d'aide \n `/role nouveau`\n       - créer un nouveau rôle"
help_text_en = "\n `/role aide` - Pour de l'aide en français\n---\n\n `/role help`\n       - show usage information and help text\n `/role new`\n       - create a new role\n"


def test_role_command_handles_empty_command_EN_client():
    # test that the role command handles empty commands in English
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    command = {
        "text": "",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }

    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_en)


def test_role_command_handles_empty_command_FR_client():
    # test that the role command handles empty commands in French
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")
    command = {
        "text": "",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_fr)


def test_role_command_handles_help_EN_command_EN_client():
    # test that role command displays help text in English
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    command = {
        "text": "help",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_en)


def test_role_command_handles_help_EN_command_FR_client():
    # test that the role command displays help text in French
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    command = {
        "text": "help",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_en)


def test_role_command_handles_help_FR_command_EN_client():
    # test that the role command displays help text in French when the french help text is used
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    command = {
        "text": "aide",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(help_text_fr)


def test_role_command_handles_unknown_command_EN_client():
    # test handling unknown command with English locale
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    command = {
        "text": "foo",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(
        "Sorry but I don't understand this command. Please type /role help to get usage information"
    )


def test_role_command_handles_unknown_command_FR_client():
    # test handling unknown command with French locale
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")
    command = {
        "text": "foo",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(
        ack,
        command,
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called()
    respond.assert_called_with(
        "Désolé mais je ne comprends pas cette commande. Veuillez saisir /role aide pour obtenir des informations sur l'utilisation"
    )


@patch("modules.role.role.request_start_modal")
def test_role_command_handles_new_role_EN_command(request_start_modal):
    # test handling new command with English locale
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    command = {
        "text": "new",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(ack, command, respond, client, body)
    ack.assert_called()
    request_start_modal.assert_called_with(client, body, locale="en-US")


@patch("modules.role.role.request_start_modal")
def test_role_command_handles_new_role_FR_command(request_start_modal):
    # test handling role new command with French locale
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    command = {
        "text": "nouveau",
        "command": "/role",
        "user_id": "user_id",
        "user_name": "user_name",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
    }
    role.role_command(ack, command, respond, client, body)
    ack.assert_called()
    request_start_modal.assert_called_with(client, body, locale="fr-FR")


@patch("modules.role.role.role_modal_view")
def test_role_action_update_locale_to_FR(role_modal_view):
    # test updating the modal view to French
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")

    role.update_modal_locale(ack, client, body)
    ack.assert_called()
    role_modal_view.assert_called_with("fr-FR")


@patch("modules.role.role.role_modal_view")
def test_role_action_update_locale_to_EN(role_modal_view):
    # test updating the modal view to English
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR")

    role.update_modal_locale(ack, client, body)
    ack.assert_called()
    role_modal_view.assert_called_with("en-US")


def test_request_start_modal():
    # test starting the modal view
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
    # test updating modal locale to English from French
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR")

    role.update_modal_locale(ack, client, body)
    args = client.views_update.call_args_list
    _, kwargs = args[0]
    ack.assert_called()
    assert kwargs["view"]["blocks"][0]["elements"][0]["value"] == "en-US"


def test_update_modal_locale_to_FR():
    # test updating modal locale to French from English
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")

    role.update_modal_locale(ack, client, body)
    args = client.views_update.call_args_list
    _, kwargs = args[0]
    ack.assert_called()
    assert kwargs["view"]["blocks"][0]["elements"][0]["value"] == "fr-FR"


@patch.object(role, "INTERNAL_TALENT_FOLDER", "internal_talent_folder")
@patch("modules.role.role.BOT_EMAIL", "bot_email")
@patch("modules.role.role.ROLE_SCOPES", ["https://www.googleapis.com/auth/drive"])
@patch("modules.role.role.google_drive.copy_file_to_folder")
@patch("modules.role.role.google_drive.create_folder")
def test_create_new_folder(mock_create_new_folder, mock_copy_file_to_folder):
    # test creating a new folder
    ack = MagicMock()
    say = MagicMock()
    body = helper_body_payload("en-US")
    client = MagicMock()
    mock_create_new_folder.return_value = {"id": "id"}
    role.role_view_handler(ack, body, say, client)
    mock_create_new_folder.assert_called_once_with(
        "foo",
        "internal_talent_folder",
        "id",
        scopes=["https://www.googleapis.com/auth/drive"],
        delegated_user_email="bot_email",
    )


@patch.multiple(role, **ROLE_CONSTANTS)  # type: ignore
@patch("modules.role.role.BOT_EMAIL", "bot_email")
@patch("modules.role.role.ROLE_SCOPES", ["https://www.googleapis.com/auth/drive"])
@patch("modules.role.role.logger")
@patch("modules.role.role.google_drive.create_folder")
@patch("modules.role.role.google_drive.copy_file_to_folder")
def test_copy_files_to_internal_talent_folder(
    mock_copy_file_to_folder, mock_create_new_folder, mock_logger
):
    # test copying files to internal talent folder
    ack = MagicMock()
    say = MagicMock()
    body = helper_body_payload("en-US")
    client = MagicMock()
    mock_create_new_folder.return_value = {"id": "folder_id"}
    mock_copy_file_to_folder.return_value = "id"
    role.role_view_handler(ack, body, say, client)
    mock_copy_file_to_folder.assert_has_calls(
        [
            call(
                "scoring_guide_template",
                "Template 2022/06 - foo Interview Panel Scoring Document - <year/month> ",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "core_values_template",
                "Template EN+FR 2022/09- foo - Core Values Panel - Interview Guide - <year/month> - <candidate initials> ",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "technical_interview_template",
                "Template EN+FR 2022/09 - foo - Technical Panel - Interview Guide - <year/month> - <candidate initials> ",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "intake_form_template",
                "TEMPLATE Month YYYY - foo - Kick-off form",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "phone_screen_template",
                "Phone Screen - Template",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "recruitment_feedback_template",
                "Recruitment Feedback - foo",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
            call(
                "panelist_guidebook_template",
                "Panelist Guidebook - Interview Best Practices - foo",
                "mock_templates_folder",
                "folder_id",
                scopes=["https://www.googleapis.com/auth/drive"],
                delegated_user_email="bot_email",
            ),
        ]
    )

    # 1 call for the handler
    # 1 call for the folder creation
    # 7 calls for copying files
    # 1 call for conversation creation
    assert mock_logger.info.call_count == 10


@patch("modules.role.role.i18n")
@patch("integrations.slack.users.get_user_locale")
def test_role_update_modal_locale_ack(mock_get_user_locale, mock_i18n):
    # test ack is called when modal is submitted
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")
    role.update_modal_locale(ack, client, body)
    ack.assert_called_once()


@patch("modules.role.role.role_modal_view")
def test_role_modal_view(mock_role_modal_view):
    # test role_modal_view is called when modal is submitted
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")
    role.update_modal_locale(ack, client, body)
    ack.assert_called()
    mock_role_modal_view.assert_called_once()


@patch("modules.role.role.google_drive.create_folder")
@patch("modules.role.role.google_drive.copy_file_to_folder")
def test_role_creates_channel_and_sets_topic_and_announces_channel(
    mock_copy_file_to_folder, mock_create_new_folder
):
    # test that a private channel is created, the topic is set and the channel is announced
    ack = MagicMock()
    say = MagicMock()
    body = helper_body_payload("en-US")
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    mock_create_new_folder.return_value = {"id": "folder_id"}
    role.role_view_handler(ack, body, say, client)

    client.conversations_create.assert_called_once_with(name="bar", is_private=True)
    client.conversations_setTopic.assert_called_once_with(
        channel="channel_id",
        topic=f"Channel for foo\nScoring Guide: https://docs.google.com/spreadsheets/d/{mock_copy_file_to_folder.return_value}",
    )
    say.assert_any_call(
        text="<@user_id> has created a new channel for foo with channel name channel_name in <#channel_id>\n",
        channel="channel_id",
    )


# test that indicated users are invited to the channel
@patch("modules.role.role.google_drive.create_folder")
@patch("modules.role.role.google_drive.copy_file_to_folder")
def test_role_add_invited_users_to_channel(
    mock_copy_file_to_folder, mock_create_new_folder
):
    ack = MagicMock()
    say = MagicMock()
    body = helper_body_payload("en-US")
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {"id": "user_id", "profile": {"display_name_normalized": "name"}},
    }
    mock_create_new_folder.return_value = {"id": "folder_id"}
    role.role_view_handler(ack, body, say, client)
    client.conversations_invite.assert_called_with(
        channel="channel_id", users="user_id"
    )


def helper_client_locale(locale=""):
    # helper function to set the user locale.
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
    # helper function to construct the body payload
    return {
        "user": {"id": "user_id"},
        "view": {
            "id": "view_id",
            "state": {
                "values": {
                    "role_name": {"role_name": {"value": "foo"}},
                    "channel_name": {"channel_name": {"value": "bar"}},
                    "users_invited": {
                        "users_invited": {"selected_users": {"user_id": "user_id"}}
                    },
                }
            },
        },
        "actions": [{"action_id": "role_change_locale", "value": locale}],
    }
