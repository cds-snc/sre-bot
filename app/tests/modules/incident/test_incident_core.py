from unittest.mock import ANY, MagicMock, call, patch
import pytest
from models.incidents import IncidentPayload
from modules.incident import core


def helper_generate_default_incident_params():
    return IncidentPayload(
        name="name",
        folder="folder",
        product="product",
        security_incident="yes",
        user_id="user_id",
        channel_id="channel_id",
        channel_name="channel_name",
        slug="slug",
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_succeeds(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet: MagicMock,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = [
        {
            "id": "U12345",
            "name": "testuser",
            "real_name": "testuser",
            "profile": {
                "email": "email@example.com",
                "real_name": "Test User",
                "display_name": "testuser",
                "display_name_normalized": "test user name",
            },
        },
    ]
    client = MagicMock()
    say = MagicMock()
    mock_create_incident_conversation.return_value = {
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    mock_google_meet.create_space.return_value = {
        "name": "spaces/asdfasdf",
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
        "meetingCode": "aaa-bbbb-ccc",
    }
    mock_incident_document.create_incident_document.return_value = (
        "document_id"  # which is used to form the url
    )
    mock_incident_folder.list_incident_folders.return_value = [
        {"id": "folder", "name": "Team Name"},
    ]
    mock_db_operations.create_incident.return_value = "incident_id"  # the id in the db
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": [
            {
                "id": "U12345",
                "name": "security_user",
                "real_name": "Security User",
                "profile": {
                    "email": "email@example.com",
                    "real_name": "Security User",
                    "display_name": "security_user",
                    "display_name_normalized": "security_user",
                },
            },
        ],
    }
    core.initiate_resources_creation(client, incident_payload)

    # this must be performed before the resources creation is called.
    client.conversations_create.assert_not_called()

    # now all the resources are called
    client.conversations_setTopic.assert_called_once_with(
        channel="channel_id", topic="Incident: name / product"
    )
    client.conversations_setPurpose.assert_called_once_with(
        channel="channel_id", purpose="name"
    )
    client.chat_postMessage.assert_any_call(
        text="<@user_id> has kicked off a new incident: name for product in <#channel_id>\n<@user_id> a initié un nouvel incident: name pour product dans <#channel_id>",
        channel=core.INCIDENT_CHANNEL,
    )
    mock_google_meet.create_space.assert_called_once()
    client.bookmarks_add.assert_has_calls(
        [
            call(
                channel_id="channel_id",
                title="Meet link",
                type="link",
                link="https://meet.google.com/aaa-bbbb-ccc",
            ),
            call(
                channel_id="channel_id",
                title="Incident report",
                type="link",
                link=ANY,  # Accept any document link since it's a MagicMock
            ),
        ]
    )
    client.conversations_canvases_create.assert_called_once_with(
        channel_id="channel_id",
        document_content={
            "type": "markdown",
            "markdown": "# Incident Canvas 📋\n\nUse this area to write/store anything you want. All you need to do is to start typing below!️",
        },
    )

    client.chat_postMessage.assert_any_call(
        text="A hangout has been created at: https://meet.google.com/aaa-bbbb-ccc",
        channel="channel_id",
    )

    mock_incident_document.create_incident_document.assert_called_once_with(
        "slug", "folder"
    )

    mock_incident_folder.add_new_incident_to_list.assert_called_once_with(
        "https://docs.google.com/document/d/document_id/edit",
        "name",
        "slug",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
    )

    mock_db_operations.create_incident.assert_called_once_with(
        {
            "channel_id": "channel_id",
            "channel_name": "channel_name",
            "name": "name",
            "user_id": "user_id",
            "teams": ["Team Name"],
            "report_url": "https://docs.google.com/document/d/document_id/edit",
            "meet_url": "https://meet.google.com/aaa-bbbb-ccc",
            "environment": "prod",
        }
    )

    client.bookmarks_add.assert_has_calls(
        [
            call(
                channel_id="channel_id",
                title="Incident report",
                type="link",
                link="https://docs.google.com/document/d/document_id/edit",
            ),
        ],
        any_order=True,
    )

    client.chat_postMessage.assert_any_call(
        text=":lapage: An incident report has been created at: https://docs.google.com/document/d/document_id/edit",
        channel="channel_id",
    )

    client.chat_postMessage.assert_any_call(
        text="Run `/sre incident roles` to assign roles to the incident",
        channel="channel_id",
    )
    client.chat_postMessage.assert_any_call(
        text="Run `/sre incident close` to update the status of the incident document and incident spreadsheet to closed and to archive the channel",
        channel="channel_id",
    )
    client.chat_postMessage.assert_any_call(
        text="Run `/sre incident schedule` to let the SRE bot schedule a Retro Google calendar meeting for all participants.",
        channel="channel_id",
    )

    mock_incident_document.update_boilerplate_text.assert_called_once_with(
        "document_id",
        "name",
        "product",
        "https://gcdigital.slack.com/archives/channel_id",
        "test user name",
    )
    mock_logger.info.assert_any_call(
        "incident_record_created", incident_id="incident_id"
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_oncall_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.side_effect = Exception("oncall error")
    client = MagicMock()
    say = MagicMock()
    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "oncall error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_not_called()
    mock_incident_document.create_incident_document.assert_not_called()
    mock_incident_folder.add_new_incident_to_list.assert_not_called()
    mock_db_operations.create_incident.assert_not_called()
    mock_logger.info.assert_not_called()


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_meet_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.side_effect = Exception("meet error")
    client = MagicMock()
    say = MagicMock()
    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "meet error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_not_called()
    mock_incident_folder.add_new_incident_to_list.assert_not_called()
    mock_db_operations.create_incident.assert_not_called()
    mock_logger.info.assert_not_called()


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_document_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.side_effect = Exception("doc error")
    client = MagicMock()
    say = MagicMock()
    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "doc error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with(
        "slug", "folder"
    )
    mock_incident_folder.add_new_incident_to_list.assert_not_called()
    mock_db_operations.create_incident.assert_not_called()
    mock_logger.info.assert_not_called()


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_db_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.side_effect = Exception("db error")
    client = MagicMock()
    say = MagicMock()
    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "db error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with(
        "slug", "folder"
    )
    mock_incident_folder.add_new_incident_to_list.assert_called_once()
    mock_logger.info.assert_any_call("incident_document_created", document_id="doc_id")


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_security_group_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "yes"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    say = MagicMock()
    client.usergroups_users_list.side_effect = Exception("security error")
    try:
        core.initiate_resources_creation(client, incident_payload)
    except Exception as e:
        assert str(e) == "security error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with(
        "slug", "folder"
    )
    mock_incident_folder.add_new_incident_to_list.assert_called_once()
    mock_db_operations.create_incident.assert_called_once()
    mock_logger.info.assert_any_call("incident_document_created", document_id="doc_id")
    mock_logger.info.assert_any_call(
        "incident_record_created", incident_id="incident_id"
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_no_users_to_invite(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = [
        {
            "id": "user_id",
            "name": "testuser",
            "real_name": "testuser",
            "profile": {
                "email": "email@example.com",
                "real_name": "Test User",
                "display_name": "testuser",
                "display_name_normalized": "test user name",
            },
        },  # same as creator, so no one to invite --- IGNORE ---
    ]
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    say = MagicMock()
    client.usergroups_users_list.return_value = {"ok": True, "users": ["user_id"]}
    core.initiate_resources_creation(client, incident_payload)
    client.conversations_invite.assert_called_once_with(
        channel="channel_id", users="user_id"
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_boilerplate_update_fails(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    mock_incident_document.update_boilerplate_text.side_effect = Exception(
        "boilerplate error"
    )
    client = MagicMock()
    say = MagicMock()
    try:
        core.initiate_resources_creation(client, incident_payload)
    except Exception as e:
        assert str(e) == "boilerplate error"
