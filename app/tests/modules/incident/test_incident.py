import datetime

import os

from modules import incident

from unittest.mock import call, MagicMock, patch, ANY

DATE = datetime.datetime.now().strftime("%Y-%m-%d")


def test_is_floppy_disk_true():
    # Test case where the reaction is 'floppy_disk'
    event = {"reaction": "floppy_disk"}
    assert (
        incident.is_floppy_disk(event) is True
    ), "The function should return True for 'floppy_disk' reaction"


def test_is_floppy_disk_false():
    # Test case where the reaction is not 'floppy_disk'
    event = {"reaction": "thumbs_up"}
    assert (
        incident.is_floppy_disk(event) is False
    ), "The function should return False for reactions other than 'floppy_disk'"


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
        "Submit",
        "Launching incident process...",
    ]
    mock_get_user_locale.return_value = "en-US"
    mock_list_incident_folders.return_value = [{"id": "id", "name": "name"}]
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
    assert kwargs["view"]["title"]["text"] == "SRE - Start an incident"
    assert kwargs["view"]["submit"]["text"] == "Submit"
    assert (
        kwargs["view"]["blocks"][0]["text"]["text"]
        == ":beach-ball: Launching incident process..."
    )
    mock_generate_incident_modal_view.assert_called_once_with(command, ANY, "en-US")
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
    incident.open_modal(client, ack, command, body)
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
    incident.open_modal(client, ack, command, body)
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
    incident.open_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_get_user_locale.assert_called_once_with(client, "user_id")
    mock_generate_incident_modal_view.assert_called_once_with(command, ANY, "fr-FR")


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
    incident.open_modal(client, ack, command, body)
    ack.assert_called_once()
    mock_i18n.t.assert_called()


@patch("modules.incident.incident.i18n")
@patch("integrations.slack.users.get_user_locale")
@patch("modules.incident.incident.incident_folder.list_incident_folders")
def test_incident_locale_button_calls_ack(
    mock_list_incident_folders, mock_get_user_locale, mock_i18n
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

    ack.assert_called
    mock_generate_incident_modal_view.assert_called_with(command, options, "en-US")


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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_calls_ack(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    _mock_google_meet,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_called()


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.generate_success_modal")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_calls_views_open(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    _mock_generate_success_modal,
    _mock_google_meet,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "user_id"}, "trigger_id": "trigger_id", "view": view}
    client = MagicMock()
    incident.submit(ack, view, say, body, client, logger)
    ack.assert_called_once()
    client.views_open.assert_called_once()


@patch("modules.incident.incident.GoogleMeet")
def test_incident_submit_returns_error_if_description_is_not_alphanumeric(
    _mock_google_meet,
):
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


@patch("modules.incident.incident.GoogleMeet")
def test_incident_submit_returns_error_if_description_is_too_long(
    _mock_google_meet,
):
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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_creates_channel_sets_topic_and_announces_channel(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    _mock_google_meet,
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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_creates_channel_sets_description(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    _mock_google_meet,
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
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id", purpose="name"
    )


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_adds_creator_to_channel(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    _mock_google_meet,
):
    ack = MagicMock()
    logger = MagicMock()
    view = helper_generate_view()
    say = MagicMock()
    body = {"user": {"id": "creator_user_id"}, "view": view, "trigger_id": "trigger_id"}
    client = MagicMock()
    client.views_open.return_value = {"view": view}
    client.conversations_create.return_value = {
        "channel": {"id": "channel_id", "name": "channel_name"}
    }
    client.usergroups_users_list.return_value = {
        "ok": False,
    }
    client.users_lookupByEmail.return_value = {"ok": False, "error": "users_not_found"}
    incident.submit(ack, view, say, body, client, logger)
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
        ]
    )


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_adds_bookmarks_for_a_meet_and_announces_it(
    _log_to_sentinel_mock,
    _mock_get_folder_metadata,
    _mock_create_incident_document,
    _mock_update_boilerplate_text,
    _mock_add_new_incident_to_list,
    mock_google_meet,
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
    mock_google_meet_instance = mock_google_meet.return_value
    mock_google_meet_instance.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
        "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
    }
    incident.submit(ack, view, say, body, client, logger)

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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_creates_a_document_and_announces_it(
    _log_to_sentinel_mock,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_add_new_incident_to_list,
    mock_google_meet,
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
    mock_add_new_incident_to_list.assert_called_once_with(
        "https://docs.google.com/document/d/id/edit",
        "name",
        f"{DATE}-name",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
    )


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_pulls_oncall_people_into_the_channel(
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_add_new_incident_to_list,
    mock_google_meet,
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
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "security_user_id_1",
            "security_user_id_2",
        ],
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_does_not_invite_on_call_if_already_in_channel(
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_add_new_incident_to_list,
    mock_google_meet,
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

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
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


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
def test_incident_submit_does_not_invite_security_group_members_already_in_channel(
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_add_new_incident_to_list,
    mock_google_meet,
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
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "creator_user_id",
            "security_user_id_2",
        ],
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
    client.conversations_invite.assert_has_calls(
        [
            call(channel="channel_id", users="creator_user_id"),
            call(channel="channel_id", users=["on_call_user_id", "security_user_id_2"]),
        ]
    )


@patch("modules.incident.incident.GoogleMeet")
@patch("modules.incident.incident.incident_folder.add_new_incident_to_list")
@patch("modules.incident.incident.incident_document.update_boilerplate_text")
@patch("modules.incident.incident.incident_document.create_incident_document")
@patch("modules.incident.incident.incident_folder.get_folder_metadata")
@patch("modules.incident.incident.opsgenie.get_on_call_users")
@patch("modules.incident.incident.log_to_sentinel")
@patch.dict(os.environ, {"PREFIX": "dev"})
def test_incident_submit_does_not_invite_security_group_members_if_prefix_dev(
    _log_to_sentinel_mock,
    mock_get_on_call_users,
    mock_list_metadata,
    mock_create_new_incident,
    mock_merge_data,
    mock_add_new_incident_to_list,
    mock_google_meet,
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
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            "creator_user_id",
        ],
    }

    mock_create_new_incident.return_value = "id"

    mock_get_on_call_users.return_value = ["email"]
    mock_list_metadata.return_value = {"appProperties": {"genie_schedule": "oncall"}}

    incident.submit(ack, view, say, body, client, logger)
    mock_get_on_call_users.assert_called_once_with("oncall")
    client.users_lookupByEmail.assert_any_call(email="email")
    client.usergroups_users_list(usergroup="SLACK_SECURITY_USER_GROUP_ID")
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
            }
        },
    }
