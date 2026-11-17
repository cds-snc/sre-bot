from collections.abc import Callable, Iterator
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from models.incidents import IncidentPayload
from modules.incident import core

# The incident slice initiate_resources_creation reads when it runs; each test starts from these values.
_SETTINGS = SimpleNamespace(
    announcement_channel_id="",
    security_group_id="S0SECURITYDEFAULT",
    policy_group_id="S0POLICYDEFAULT",
    notify_management_group_id="S0NOTIFYDEFAULT",
)


_SLACK_SETTINGS = SimpleNamespace(tenant=SimpleNamespace(team_id="T0TEAM"))


@pytest.fixture(autouse=True)
def _incident_settings() -> Iterator[None]:
    """Stub the incident slice and the Slack tenant the declare path reads at call time."""
    with (
        patch("modules.incident.core.get_incident_response_settings", return_value=_SETTINGS),
        patch("modules.incident.core.get_slack_settings", return_value=_SLACK_SETTINGS),
    ):
        yield


def test_channel_url_is_a_slack_deep_link_into_the_tenant() -> None:
    """The link names the configured workspace, never a workspace host written in code."""
    assert core.channel_url("C0123") == "https://slack.com/app_redirect?channel=C0123&team=T0TEAM"


def test_channel_url_without_a_tenant_leaves_the_workspace_to_slack() -> None:
    with patch("modules.incident.core.get_slack_settings", return_value=SimpleNamespace(tenant=None)):
        assert core.channel_url("C0123") == "https://slack.com/app_redirect?channel=C0123"


def test_channel_url_with_an_enterprise_only_tenant_leaves_the_workspace_to_slack() -> None:
    """An org-wide tenant names no single workspace, so the link carries none."""
    tenant = SimpleNamespace(team_id=None, enterprise_id="E0ORG")
    with patch("modules.incident.core.get_slack_settings", return_value=SimpleNamespace(tenant=tenant)):
        assert core.channel_url("C0123") == "https://slack.com/app_redirect?channel=C0123"


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


def _mock_successful_dependencies(
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
):
    mock_get_on_call_users_from_folder.return_value = [
        {
            "id": "U12345",
            "profile": {
                "display_name_normalized": "test user name",
            },
        },
    ]
    mock_google_meet.create_space.return_value = {
        "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
    }
    mock_incident_document.create_incident_document.return_value = "document_id"
    mock_incident_folder.list_incident_folders.return_value = [
        {"id": "folder", "name": "Team Name"},
    ]
    mock_db_operations.create_incident.return_value = "incident_id"


@patch.object(_SETTINGS, "announcement_channel_id", "incident-channel")
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
    set_environment,
):
    set_environment("production")

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
    mock_incident_document.create_incident_document.return_value = "document_id"  # which is used to form the url
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
    expected_text = """🚨 *Incident Resources Created Successfully!*
*Next Steps - Available Commands:*
• `/sre incident roles manage` - Assign roles to the incident
• `/sre incident schedule retro` - Schedule a retrospective meeting
• `/sre incident close` - Close and archive this incident
• `/sre incident status update <status>` - Update incident status
• `/sre incident status-update` - Draft, review and approve a public status update
• `/sre incident show` - View incident details
• `/sre incident summarize` - Summarize the channel to catch up someone joining the incident (optionally add `--since 30m` or `--since 2h` to limit the time range)
• `/sre incident draft` - Draft an incident report from this channel into a new document, ready for you to review and edit

*Quick Actions:*
📋 Use the bookmarked incident report above to document findings
👥 Assign roles to team members for clear responsibilities
📅 Schedule a retro meeting when ready

_Type_ `/sre incident help` _for complete command list_"""
    core.initiate_resources_creation(client, incident_payload)

    # this must be performed before the resources creation is called.
    client.conversations_create.assert_not_called()

    # now all the resources are called
    client.conversations_setTopic.assert_called_once_with(channel="channel_id", topic="Incident: name / product")
    client.conversations_setPurpose.assert_called_once_with(channel="channel_id", purpose="name")
    client.chat_postMessage.assert_any_call(
        text="<@user_id> has kicked off a new incident: name for product in <#channel_id>\n<@user_id> a initié un nouvel incident: name pour product dans <#channel_id>",
        channel="incident-channel",
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

    mock_incident_document.create_incident_document.assert_called_once_with("slug", "folder")

    mock_incident_folder.add_new_incident_to_list.assert_called_once_with(
        "https://docs.google.com/document/d/document_id/edit",
        "name",
        "slug",
        "product",
        "https://slack.com/app_redirect?channel=channel_id&team=T0TEAM",
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
            "severity": None,
            "security_incident": True,
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
        text=expected_text,
        channel="channel_id",
    )

    mock_incident_document.update_boilerplate_text.assert_called_once_with(
        "document_id",
        "name",
        "product",
        "https://slack.com/app_redirect?channel=channel_id&team=T0TEAM",
        "test user name",
    )
    mock_logger.info.assert_any_call("incident_record_created", incident_id="incident_id")


@pytest.mark.parametrize(
    ("environment", "expected_label"),
    [("production", "prod"), ("local", "dev"), ("ci", "dev")],
)
@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
def test_initiate_resources_creation_labels_record_environment(
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
    environment,
    expected_label,
    set_environment,
):
    """The stored incident is labelled prod only in production; every other environment stores dev.

    Google, Meet and the database are stubbed; the assertion reads the environment
    field of the record handed to the database, which is what downstream reports filter on.
    """
    set_environment(environment)
    _mock_successful_dependencies(
        mock_incident_folder,
        mock_incident_document,
        mock_google_meet,
        mock_db_operations,
        mock_get_on_call_users_from_folder,
    )

    core.initiate_resources_creation(MagicMock(), helper_generate_default_incident_params())

    record = mock_db_operations.create_incident.call_args.args[0]
    assert record["environment"] == expected_label


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
def test_initiate_resources_creation_adds_source_alert_link(
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    incident_payload.source_alert_permalink = "https://slack/source"
    client = MagicMock()
    _mock_successful_dependencies(
        mock_incident_folder,
        mock_incident_document,
        mock_google_meet,
        mock_db_operations,
        mock_get_on_call_users_from_folder,
    )

    core.initiate_resources_creation(client, incident_payload)

    client.bookmarks_add.assert_any_call(
        channel_id="channel_id",
        title="Source alert",
        type="link",
        link="https://slack/source",
    )
    client.chat_postMessage.assert_any_call(
        text="Source alert: <https://slack/source|View original alert>",
        channel="channel_id",
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
def test_initiate_resources_creation_skips_source_alert_link_when_missing(
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    client = MagicMock()
    _mock_successful_dependencies(
        mock_incident_folder,
        mock_incident_document,
        mock_google_meet,
        mock_db_operations,
        mock_get_on_call_users_from_folder,
    )

    core.initiate_resources_creation(client, incident_payload)

    assert not any(call.kwargs.get("title") == "Source alert" for call in client.bookmarks_add.call_args_list)
    assert not any(call.kwargs.get("text", "").startswith("Source alert:") for call in client.chat_postMessage.call_args_list)


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

    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "doc error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with("slug", "folder")
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

    with pytest.raises(Exception) as excinfo:
        core.initiate_resources_creation(client, incident_payload)
    assert str(excinfo.value) == "db error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with("slug", "folder")
    mock_incident_folder.add_new_incident_to_list.assert_called_once()
    mock_logger.info.assert_any_call("incident_document_created", document_id="doc_id")


@patch.object(_SETTINGS, "security_group_id", "S0SECURITY")
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

    client.usergroups_users_list.side_effect = Exception("security error")
    try:
        core.initiate_resources_creation(client, incident_payload)
    except Exception as e:
        assert str(e) == "security error"
    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with("slug", "folder")
    mock_incident_folder.add_new_incident_to_list.assert_called_once()
    mock_db_operations.create_incident.assert_called_once()
    mock_logger.info.assert_any_call("incident_document_created", document_id="doc_id")
    mock_logger.info.assert_any_call("incident_record_created", incident_id="incident_id")


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

    client.usergroups_users_list.return_value = {"ok": True, "users": ["user_id"]}
    core.initiate_resources_creation(client, incident_payload)
    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")


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
    mock_incident_document.update_boilerplate_text.side_effect = Exception("boilerplate error")
    client = MagicMock()

    try:
        core.initiate_resources_creation(client, incident_payload)
    except Exception as e:
        assert str(e) == "boilerplate error"


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_notify_group_added(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    incident_payload.product = "Notify"
    incident_payload.security_incident = "no"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": ["notify_user_1", "notify_user_2"],
    }
    with patch.object(_SETTINGS, "notify_management_group_id", "NOTIFY_GROUP_ID"):
        core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_called_once_with(usergroup="NOTIFY_GROUP_ID")
    assert client.conversations_invite.call_count == 2
    client.conversations_invite.assert_any_call(channel="channel_id", users=["notify_user_1", "notify_user_2"])


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_notify_group_not_added_for_other_products(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    incident_payload.product = "SomeOtherProduct"
    incident_payload.security_incident = "no"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_not_called()
    # conversations_invite is still called once to add the incident creator
    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_initiate_resources_creation_notify_group_fails(
    mock_create_incident_conversation,
    mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
):
    incident_payload = helper_generate_default_incident_params()
    incident_payload.product = "Notify"
    incident_payload.security_incident = "no"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    client.usergroups_users_list.side_effect = Exception("notify group error")
    with patch.object(_SETTINGS, "notify_management_group_id", "NOTIFY_GROUP_ID"):
        try:
            core.initiate_resources_creation(client, incident_payload)
        except Exception as e:
            assert str(e) == "notify group error"

    mock_create_incident_conversation.assert_not_called()
    mock_google_meet.create_space.assert_called_once()
    mock_incident_document.create_incident_document.assert_called_once_with("slug", "folder")
    mock_incident_folder.add_new_incident_to_list.assert_called_once()
    mock_db_operations.create_incident.assert_called_once()
    mock_logger.info.assert_any_call("incident_document_created", document_id="doc_id")
    mock_logger.info.assert_any_call("incident_record_created", incident_id="incident_id")


# --- notify_management_group_id-specific tests ---


def _notify_incident_payload():
    payload = helper_generate_default_incident_params()
    payload.product = "Notify"
    payload.security_incident = "no"
    return payload


def _setup_notify_mocks(mock_incident_document, mock_google_meet, mock_db_operations, mock_get_on_call):
    mock_get_on_call.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_notify_incident_group_id_not_set_skips_usergroups_call(
    _mock_conversation,
    _mock_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call,
    _mock_logger,
):
    """When notify_management_group_id is None, usergroups_users_list is never called."""
    incident_payload = _notify_incident_payload()
    _setup_notify_mocks(mock_incident_document, mock_google_meet, mock_db_operations, mock_get_on_call)
    client = MagicMock()

    with patch.object(_SETTINGS, "notify_management_group_id", None):
        core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_not_called()


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_notify_incident_slack_api_returns_ok_false_does_not_invite(
    _mock_conversation,
    _mock_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call,
    mock_logger,
):
    """When Slack returns ok=False, no notify users are invited and a warning is logged."""
    incident_payload = _notify_incident_payload()
    _setup_notify_mocks(mock_incident_document, mock_google_meet, mock_db_operations, mock_get_on_call)
    client = MagicMock()
    client.usergroups_users_list.return_value = {
        "ok": False,
        "error": "no_such_subteam",
    }

    with patch.object(_SETTINGS, "notify_management_group_id", "NOTIFY_GROUP_ID"):
        core.initiate_resources_creation(client, incident_payload)

    # Only the creator invite should happen, no batch notify invite
    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")
    mock_logger.warning.assert_called_once_with(
        "notify_mgmt_group_fetch_failed",
        error="no_such_subteam",
        usergroup="NOTIFY_GROUP_ID",
    )


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_notify_incident_creator_excluded_from_notify_group_invite(
    _mock_conversation,
    _mock_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call,
    _mock_logger,
):
    """The incident creator (user_id) is not duplicated in the notify group invite."""
    incident_payload = _notify_incident_payload()
    _setup_notify_mocks(mock_incident_document, mock_google_meet, mock_db_operations, mock_get_on_call)
    client = MagicMock()
    # Slack returns user_id as a member of the notify group
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": ["user_id", "notify_user_1"],
    }

    with patch.object(_SETTINGS, "notify_management_group_id", "NOTIFY_GROUP_ID"):
        core.initiate_resources_creation(client, incident_payload)

    # Only notify_user_1 should be in the batch invite (user_id excluded)
    client.conversations_invite.assert_any_call(channel="channel_id", users=["notify_user_1"])


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_notify_incident_empty_group_does_not_batch_invite(
    _mock_conversation,
    _mock_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call,
    _mock_logger,
):
    """When the notify group has no users, no batch invite is made."""
    incident_payload = _notify_incident_payload()
    _setup_notify_mocks(mock_incident_document, mock_google_meet, mock_db_operations, mock_get_on_call)
    client = MagicMock()
    client.usergroups_users_list.return_value = {"ok": True, "users": []}

    with patch.object(_SETTINGS, "notify_management_group_id", "NOTIFY_GROUP_ID"):
        core.initiate_resources_creation(client, incident_payload)

    # Only the creator invite should happen, no second batch invite
    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")


@patch.object(_SETTINGS, "security_group_id", "S0SECURITY")
@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_contract_security_group_invite_uses_environment_not_prefix(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
    set_environment,
):
    """Security users must not be invited when ENVIRONMENT is not production."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "yes"
    incident_payload.product = "SomeOtherProduct"

    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"

    client = MagicMock()
    client.usergroups_users_list.return_value = {
        "ok": True,
        "users": ["security_user_1", "security_user_2"],
    }

    set_environment("local")

    core.initiate_resources_creation(client, incident_payload)

    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")


@patch.object(_SETTINGS, "security_group_id", None)
@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_security_incident_without_a_configured_security_group_skips_the_group_invite(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
    set_environment,
):
    """With no security user group configured, declaring a security incident still completes.

    The Slack client is a mock so a group lookup would be recorded: none is made,
    a warning is logged, and only the declaring user is invited.
    """
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "yes"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    set_environment("production")

    core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_not_called()
    mock_logger.warning.assert_any_call("security_user_group_not_configured", channel_id="channel_id")
    client.conversations_invite.assert_called_once_with(channel="channel_id", users="user_id")


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_policy_help_in_production_invites_the_policy_group_once_per_user(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
    set_environment,
):
    """Policy help invites the policy group's members except the declarer, and a user in both groups is invited once."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.policy_help = "yes"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    incident_payload.security_incident = "yes"
    client.usergroups_users_list.return_value = {"ok": True, "users": ["user_id", "shared_user"]}
    set_environment("production")

    core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_any_call(usergroup="S0POLICYDEFAULT")
    client.conversations_invite.assert_called_with(channel="channel_id", users=["shared_user"])


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_no_policy_help_never_looks_up_the_policy_group(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
    set_environment,
):
    """Answering no to policy help makes no user group lookup."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "no"
    incident_payload.policy_help = "no"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    set_environment("production")

    core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_not_called()


@patch.object(_SETTINGS, "policy_group_id", "")
@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_policy_help_without_a_configured_policy_group_skips_the_group_invite(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    mock_logger,
    set_environment,
):
    """With no policy user group configured, the incident still completes: no lookup is made and a warning is logged."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "no"
    incident_payload.policy_help = "yes"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()
    set_environment("production")

    core.initiate_resources_creation(client, incident_payload)

    client.usergroups_users_list.assert_not_called()
    mock_logger.warning.assert_any_call("policy_user_group_not_configured", channel_id="channel_id")


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_declare_stores_security_incident_true_for_yes(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    """When security_incident is 'yes', it is stored as True in the database."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "yes"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    core.initiate_resources_creation(client, incident_payload)

    call_kwargs = mock_db_operations.create_incident.call_args.kwargs
    incident_data = (
        call_kwargs.get("incident_data") if "incident_data" in call_kwargs else mock_db_operations.create_incident.call_args[0][0]
    )
    assert incident_data.get("security_incident") is True


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_declare_stores_security_incident_false_for_no(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    """When security_incident is 'no', it is stored as False in the database."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "no"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    core.initiate_resources_creation(client, incident_payload)

    call_kwargs = mock_db_operations.create_incident.call_args.kwargs
    incident_data = (
        call_kwargs.get("incident_data") if "incident_data" in call_kwargs else mock_db_operations.create_incident.call_args[0][0]
    )
    assert incident_data.get("security_incident") is False


@patch("modules.incident.core.logger")
@patch("modules.incident.core.on_call.get_on_call_users_from_folder")
@patch("modules.incident.core.db_operations")
@patch("modules.incident.core.meet")
@patch("modules.incident.core.incident_document")
@patch("modules.incident.core.incident_folder")
@patch("modules.incident.incident_conversation.create_incident_conversation")
def test_declare_stores_security_incident_none_for_other_values(
    _mock_create_incident_conversation,
    _mock_incident_folder,
    mock_incident_document,
    mock_google_meet,
    mock_db_operations,
    mock_get_on_call_users_from_folder,
    _mock_logger,
):
    """When security_incident is any other value, it is stored as None in the database."""
    incident_payload = helper_generate_default_incident_params()
    incident_payload.security_incident = "unknown"
    mock_get_on_call_users_from_folder.return_value = []
    mock_google_meet.create_space.return_value = {"meetingUri": "meet_url"}
    mock_incident_document.create_incident_document.return_value = "doc_id"
    mock_db_operations.create_incident.return_value = "incident_id"
    client = MagicMock()

    core.initiate_resources_creation(client, incident_payload)

    call_kwargs = mock_db_operations.create_incident.call_args.kwargs
    incident_data = (
        call_kwargs.get("incident_data") if "incident_data" in call_kwargs else mock_db_operations.create_incident.call_args[0][0]
    )
    assert "security_incident" in incident_data
    assert incident_data["security_incident"] is None


@patch("modules.incident.core.logger")
@patch("modules.incident.core.db_operations")
def test_recreate_database_record_leaves_security_incident_unset(mock_db_operations, _mock_logger):
    """The recreate-missing-resources path has no security answer, so its incident data
    carries no security_incident key and the model default stores the flag as unknown."""
    mock_db_operations.create_incident.return_value = "incident_id"
    results: dict = {"success": [], "errors": []}

    core._create_database_record(
        "channel_id", "channel_name", "incident_name", "product", "user_id", "doc_link", "meet_url", results
    )

    incident_data = mock_db_operations.create_incident.call_args.args[0]
    assert "security_incident" not in incident_data


# -- policy help group invite -------------------------------------------------------------------

_POLICY_GROUP = _SETTINGS.policy_group_id
_SECURITY_GROUP = _SETTINGS.security_group_id
_NOTIFY_GROUP = _SETTINGS.notify_management_group_id
_DECLARER = "U0DECLARER"


def _policy_payload(**overrides: Any) -> IncidentPayload:
    values: dict[str, Any] = {
        "name": "name",
        "folder": "folder",
        "product": "SomeOtherProduct",
        "security_incident": "no",
        "policy_help": "no",
        "user_id": _DECLARER,
        "channel_id": "C0CHANNEL",
        "channel_name": "channel_name",
        "slug": "slug",
    }
    return IncidentPayload(**{**values, **overrides})


def _group_client(groups: dict[str, Any]) -> MagicMock:
    """Slack client whose user group lookups answer from `groups` (a user list, or a full response dict)."""
    client = MagicMock()

    def usergroups_users_list(usergroup: str) -> dict[str, Any]:
        answer = groups.get(usergroup, [])
        return answer if isinstance(answer, dict) else {"ok": True, "users": answer}

    client.usergroups_users_list.side_effect = usergroups_users_list
    return client


def _declare_with(
    client: MagicMock,
    payload: IncidentPayload,
    *,
    oncall: list[dict[str, str]] | None = None,
    logger: MagicMock | None = None,
) -> MagicMock:
    """Run the declare path with every collaborator but the Slack client stubbed; returns the database stub."""
    with ExitStack() as stack:
        stack.enter_context(patch("modules.incident.core.logger", logger or MagicMock()))
        stack.enter_context(patch("modules.incident.core.on_call.get_on_call_users_from_folder", return_value=oncall or []))
        database = stack.enter_context(patch("modules.incident.core.db_operations"))
        meet = stack.enter_context(patch("modules.incident.core.meet"))
        document = stack.enter_context(patch("modules.incident.core.incident_document"))
        stack.enter_context(patch("modules.incident.core.incident_folder"))
        meet.create_space.return_value = {"meetingUri": "meet_url"}
        document.create_incident_document.return_value = "doc_id"
        database.create_incident.return_value = "incident_id"
        core.initiate_resources_creation(client, payload)
    return database


def _batch_invites(client: MagicMock) -> list[list[str]]:
    """The invite calls that carry a list of users (the single-id call is the declarer's own join)."""
    return [c.kwargs["users"] for c in client.conversations_invite.call_args_list if isinstance(c.kwargs["users"], list)]


def _looked_up(client: MagicMock) -> list[str]:
    return [c.kwargs["usergroup"] for c in client.usergroups_users_list.call_args_list]


def _oncall(user_id: str) -> dict[str, Any]:
    return {"id": user_id, "profile": {"display_name_normalized": user_id}}


def test_policy_help_in_production_invites_the_policy_group(set_environment: Callable[[str], None]) -> None:
    """Answering yes invites every member of the configured policy group in production."""
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1", "U0POLICY2"]})

    _declare_with(client, _policy_payload(policy_help="yes"))

    assert _looked_up(client) == [_POLICY_GROUP]
    assert _batch_invites(client) == [["U0POLICY1", "U0POLICY2"]]


def test_policy_help_never_invites_the_declarer_a_second_time(set_environment: Callable[[str], None]) -> None:
    """The declaring user is already in the channel, so a policy group they belong to does not re-invite them."""
    set_environment("production")
    client = _group_client({_POLICY_GROUP: [_DECLARER, "U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help="yes"))

    assert _batch_invites(client) == [["U0POLICY1"]]


@pytest.mark.parametrize("members", [[], [_DECLARER]])
def test_a_policy_group_with_nobody_to_invite_sends_no_batch_invite(
    set_environment: Callable[[str], None], members: list[str]
) -> None:
    set_environment("production")
    client = _group_client({_POLICY_GROUP: members})

    _declare_with(client, _policy_payload(policy_help="yes"))

    assert _batch_invites(client) == []


@pytest.mark.parametrize("environment", ["ci", "staging", "local"])
def test_every_non_production_environment_skips_the_policy_invite(
    set_environment: Callable[[str], None], environment: str
) -> None:
    """Outside production the group's members are not invited, to avoid spamming real people."""
    set_environment(environment)
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help="yes"))

    assert _batch_invites(client) == []


def test_a_payload_without_a_policy_answer_defaults_to_no(set_environment: Callable[[str], None]) -> None:
    """A payload built without the field (an older submission) behaves as no policy help."""
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"]})
    payload = IncidentPayload(
        name="name",
        folder="folder",
        product="SomeOtherProduct",
        security_incident="no",
        user_id=_DECLARER,
        channel_id="C0CHANNEL",
        channel_name="channel_name",
        slug="slug",
    )

    _declare_with(client, payload)

    assert _looked_up(client) == []


@pytest.mark.parametrize("answer", ["", "YES", "true", "maybe", "1"])
def test_only_a_literal_yes_requests_policy_help(set_environment: Callable[[str], None], answer: str) -> None:
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help=answer))

    assert _looked_up(client) == []
    assert _batch_invites(client) == []


def test_an_unset_policy_group_does_not_block_a_configured_security_group(
    set_environment: Callable[[str], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    set_environment("production")
    monkeypatch.setattr(_SETTINGS, "policy_group_id", "")
    client = _group_client({_SECURITY_GROUP: ["U0SEC1"]})

    database = _declare_with(client, _policy_payload(security_incident="yes", policy_help="yes"))

    assert _batch_invites(client) == [["U0SEC1"]]
    database.create_incident.assert_called_once()


def test_a_failed_policy_group_lookup_is_logged_and_the_incident_still_completes(
    set_environment: Callable[[str], None],
) -> None:
    """A not-ok lookup response invites nobody from that group, logs the error, and does not abort creation."""
    set_environment("production")
    client = _group_client({_POLICY_GROUP: {"ok": False, "error": "usergroup_not_found"}})
    logger = MagicMock()

    database = _declare_with(client, _policy_payload(policy_help="yes"), logger=logger)

    logger.warning.assert_any_call("policy_group_fetch_failed", error="usergroup_not_found", usergroup=_POLICY_GROUP)
    assert _batch_invites(client) == []
    database.create_incident.assert_called_once()


def test_a_failed_policy_lookup_keeps_the_other_groups_invites(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_SECURITY_GROUP: ["U0SEC1"], _POLICY_GROUP: {"ok": False, "error": "ratelimited"}})

    _declare_with(client, _policy_payload(security_incident="yes", policy_help="yes"))

    assert _batch_invites(client) == [["U0SEC1"]]


def test_policy_help_does_not_need_a_security_incident(set_environment: Callable[[str], None]) -> None:
    """The two answers are independent: policy help alone looks up only the policy group."""
    set_environment("production")
    client = _group_client({_SECURITY_GROUP: ["U0SEC1"], _POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(security_incident="no", policy_help="yes"))

    assert _looked_up(client) == [_POLICY_GROUP]
    assert _batch_invites(client) == [["U0POLICY1"]]


def test_a_security_incident_alone_does_not_invite_the_policy_group(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_SECURITY_GROUP: ["U0SEC1"], _POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(security_incident="yes", policy_help="no"))

    assert _looked_up(client) == [_SECURITY_GROUP]
    assert _batch_invites(client) == [["U0SEC1"]]


def test_security_and_policy_groups_are_both_invited_in_one_call(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_SECURITY_GROUP: ["U0SEC1", "U0SEC2"], _POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(security_incident="yes", policy_help="yes"))

    assert _batch_invites(client) == [["U0SEC1", "U0SEC2", "U0POLICY1"]]


def test_a_user_in_both_the_security_and_policy_groups_is_invited_once(set_environment: Callable[[str], None]) -> None:
    """Slack rejects a duplicate id in one invite, so a shared member appears a single time."""
    set_environment("production")
    client = _group_client({_SECURITY_GROUP: ["U0SHARED", "U0SEC1"], _POLICY_GROUP: ["U0SHARED", "U0POLICY1"]})

    _declare_with(client, _policy_payload(security_incident="yes", policy_help="yes"))

    assert _batch_invites(client) == [["U0SHARED", "U0SEC1", "U0POLICY1"]]


def test_an_on_call_user_in_the_policy_group_is_invited_once(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0ONCALL", "U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help="yes"), oncall=[_oncall("U0ONCALL")])

    assert _batch_invites(client) == [["U0ONCALL", "U0POLICY1"]]


def test_on_call_users_are_invited_ahead_of_the_policy_group(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help="yes"), oncall=[_oncall("U0ONCALL1"), _oncall("U0ONCALL2")])

    assert _batch_invites(client) == [["U0ONCALL1", "U0ONCALL2", "U0POLICY1"]]


def test_policy_help_on_a_notify_incident_invites_the_notify_management_group_too(set_environment: Callable[[str], None]) -> None:
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"], _NOTIFY_GROUP: ["U0NOTIFY1"]})

    _declare_with(client, _policy_payload(product="Notify", policy_help="yes"))

    assert _looked_up(client) == [_POLICY_GROUP, _NOTIFY_GROUP]
    assert _batch_invites(client) == [["U0POLICY1", "U0NOTIFY1"]]


def test_policy_help_does_not_change_the_stored_security_flag(set_environment: Callable[[str], None]) -> None:
    """The policy answer is not persisted as the security flag: a non-security incident stays False."""
    set_environment("production")
    client = _group_client({_POLICY_GROUP: ["U0POLICY1"]})

    database = _declare_with(client, _policy_payload(security_incident="no", policy_help="yes"))

    assert database.create_incident.call_args.args[0]["security_incident"] is False


def test_the_policy_lookup_uses_the_configured_group_id(
    set_environment: Callable[[str], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    set_environment("production")
    monkeypatch.setattr(_SETTINGS, "policy_group_id", "S0OTHERPOLICY")
    client = _group_client({"S0OTHERPOLICY": ["U0POLICY1"]})

    _declare_with(client, _policy_payload(policy_help="yes"))

    assert _looked_up(client) == ["S0OTHERPOLICY"]
    assert _batch_invites(client) == [["U0POLICY1"]]
