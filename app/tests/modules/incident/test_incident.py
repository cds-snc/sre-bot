import datetime

from modules import incident

from unittest.mock import call, MagicMock, patch, ANY

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


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_calls_ack(
    _log_to_sentinel_mock,
    _mock_incident_document,
    _mock_incident_folder,
    _mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client)
    ack.assert_called()


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.generate_success_modal")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_calls_views_open(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    _mock_incident_folder,
    _mock_incident_document,
    _mock_generate_success_modal,
    _mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    incident.submit(ack, view, say, body, client)
    ack.assert_called_once()
    client.views_open.assert_called_once()


@patch("modules.incident.incident.meet")
def test_incident_submit_returns_error_if_description_is_not_alphanumeric(
    _mock_google_meet,
):
    ack = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client)
    ack.assert_any_call(
        response_action="errors",
        errors={
            "name": "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
        },
    )


@patch("modules.incident.incident.meet")
def test_incident_submit_returns_error_if_description_is_too_long(
    _mock_google_meet,
):
    ack = MagicMock()

    view = helper_generate_view("a" * 61)
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client)
    ack.assert_any_call(
        response_action="errors",
        errors={
            "name": "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
        },
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_creates_channel_sets_topic_and_announces_channel(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    _mock_incident_folder,
    _mock_incident_document,
    _mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client)
    client.conversations_create.assert_not_called()
    client.conversations_setTopic.assert_called_once_with(
        channel="channel_id", topic="Incident: name / product"
    )
    say.assert_any_call(
        text="<@user_id> has kicked off a new incident: name for product in <#channel_id>\n<@user_id> a initié un nouvel incident: name pour product dans <#channel_id>",
        channel=incident.INCIDENT_CHANNEL,
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_creates_channel_sets_description(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    _mock_incident_folder,
    _mock_incident_document,
    _mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client)
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id", purpose="name"
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_adds_creator_to_channel(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    _mock_incident_folder,
    _mock_incident_document,
    _mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "view": view, "trigger_id": "trigger_id"}
    client = MagicMock()
    client.views_open.return_value = {"view": view}
    client.usergroups_users_list.return_value = {
        "ok": False,
    }
    client.users_lookupByEmail.return_value = {"ok": False, "error": "users_not_found"}
    incident.submit(ack, view, say, body, client)
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
        ]
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_adds_bookmarks_for_a_meet_and_announces_it(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    _mock_incident_folder,
    _mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    mock_google_meet.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
        "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
    }
    incident.submit(ack, view, say, body, client)

    client.bookmarks_add.assert_any_call(
        channel_id="channel_id",
        title="Meet link",
        type="link",
        link="https://meet.google.com/aaa-bbbb-ccc",
    )
    say.assert_any_call(
        text="A hangout has been created at: https://meet.google.com/aaa-bbbb-ccc",
        channel="channel_id",
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_canvas_create_successful_called_with_correct_params(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    client = MagicMock()
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    canvas_data = {
        "type": "markdown",
        "markdown": "# Incident Canvas 📋\n\nUse this area to write/store anything you want. All you need to do is to start typing below!️",
    }

    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    mock_google_meet.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
        "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
    }
    incident.submit(ack, view, say, body, client)

    client.conversations_canvases_create.assert_called_once_with(
        channel_id="channel_id", document_content=canvas_data
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_canvas_create_returns_successful_response(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
):
    mock_incident_folder.create_item.return_value = "incident_id"
    client = MagicMock()
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    expected_response = {"ok": True, "canvas_id": "canvas_id"}
    client.conversations_canvases_create.return_value = expected_response

    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    mock_google_meet.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
        "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
    }
    incident.submit(ack, view, say, body, client)

    assert client.conversations_canvases_create.return_value == expected_response
    ack.assert_called_once()


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_canvas_create_unsuccessful_called(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
):
    mock_incident_folder.create_item.return_value = "incident_id"

    client = MagicMock()
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    expected_response = {"ok": False, "error": "invalid_type"}
    client.conversations_canvases_create.return_value = expected_response

    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    mock_google_meet.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
        "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
    }
    incident.submit(ack, view, say, body, client)

    assert client.conversations_canvases_create.return_value == expected_response


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_creates_a_document_and_announces_it(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_google_meet,
    mock_incident_document,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()

    body = {
        "user": {"id": "user_id"},
        "channel_id": {},
        "trigger_id": "trigger_id",
        "view": view,
    }
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }

    mock_incident_folder.create_item.return_value = "incident_id"

    mock_incident_document.create_incident_document.return_value = "id"

    mock_incident_folder.get_folder_metadata.return_value = {"appProperties": {}}

    incident.submit(ack, view, say, body, client)
    mock_incident_document.create_incident_document.assert_called_once_with(
        "slug", "folder"
    )

    mock_incident_folder.add_new_incident_to_list.assert_called_once_with(
        "https://docs.google.com/document/d/id/edit",
        "name",
        "slug",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
    )
    mock_incident_folder.get_folder_metadata.assert_called_once_with("folder")


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_pulls_oncall_people_into_the_channel(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "on_call_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "security_user_id_1",
            "security_user_id_2",
        ],
    }

    mock_incident_document.create_incident_document.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_incident_folder.get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "oncall"}
    }

    incident.submit(ack, view, say, body, client)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(
                channel="channel_id",
                users=["on_call_user_id", "security_user_id_1", "security_user_id_2"],
            ),
        ]
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_does_not_invite_on_call_if_already_in_channel(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "creator_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "security_user_id_1",
            "security_user_id_2",
        ],
    }

    mock_incident_document.create_incident_document.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_incident_folder.get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "oncall"}
    }

    incident.submit(ack, view, say, body, client)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(
                channel="channel_id", users=["security_user_id_1", "security_user_id_2"]
            ),
        ]
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_does_not_invite_security_group_members_already_in_channel(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "on_call_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "creator_user_id",
            "security_user_id_2",
        ],
    }

    mock_incident_document.create_incident_document.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_incident_folder.get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "oncall"}
    }

    incident.submit(ack, view, say, body, client)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users=["on_call_user_id", "security_user_id_2"]),
        ]
    )


@patch.object(incident, "PREFIX", "dev")
@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_does_not_invite_security_group_members_if_prefix_dev(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_incident_folder,
    mock_get_on_call_users,
    mock_create_new_incident,
    mock_merge_data,
    mock_google_meet,
    mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()

    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "on_call_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "creator_user_id",
        ],
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_incident_folder.get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "oncall"}
    }

    incident.submit(ack, view, say, body, client)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users=["on_call_user_id"]),
        ]
    )


@patch("modules.incident.incident.db_operations")
@patch("modules.incident.incident.meet")
@patch("modules.incident.incident.incident_document")
@patch("modules.incident.incident.incident_folder")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_incident_submit_does_not_invite_security_group_members_if_not_selected(
    mock_create_incident_conversation,
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    _mock_db_operations,
):
    ack = MagicMock()

    view = helper_generate_view()

    # override the security incident selection to "no"
    view["state"]["values"]["security_incident"]["security_incident"][
        "selected_option"
    ]["value"] = "no"

    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    client.users_lookupByEmail.return_value = {
        "ok": True,
        "user": {
            "id": "on_call_user_id",
            "profile": {"display_name_normalized": "name"},
        },
    }
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": ["creator_user_id", "security_user_id"],
    }

    mock_incident_document.create_incident_document.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_incident_folder.get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "oncall"}
    }

    incident.submit(ack, view, say, body, client)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list.assert_not_called()
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users=["on_call_user_id"]),
        ]
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
