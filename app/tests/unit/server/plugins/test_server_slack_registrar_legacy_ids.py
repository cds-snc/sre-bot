"""Unit tests for legacy-id aliases registered through a plugin's scoped Slack registrar.

Each test wraps the real Slack provider (Bolt is never started) in the registrar
the host hands one plugin. A legacy id is an alias of the plugin's new listener:
it is exempt from the entry-point prefix that the primary id must carry, it must
be non-blank and unique across block and attachment actions, it is logged once at
registration, and the provider lists it for removal. Registration errors are
asserted as raised exceptions because they abort boot.
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from integrations.slack.settings import SlackSettings
from server.plugins.slack_registrar import PluginSlackRegistrar

pytestmark = pytest.mark.unit

PLUGIN = "incident.response"


def listener(**_: Any) -> None:
    """Stand-in Bolt listener."""


@pytest.fixture
def provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
    return SlackPlatformProvider(settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter())


@pytest.fixture
def registrar(provider: SlackPlatformProvider) -> PluginSlackRegistrar:
    return PluginSlackRegistrar(provider, PLUGIN)


def test_legacy_ids_are_listed_against_their_new_id(provider: SlackPlatformProvider, registrar: PluginSlackRegistrar) -> None:
    registrar.register_block_action(f"{PLUGIN}.acknowledge", listener, legacy_action_ids=("ack_incident",))
    registrar.register_attachment_action(f"{PLUGIN}.alert", listener, legacy_callback_ids=("handle_incident_action_buttons",))

    assert provider.legacy_ids() == {
        "ack_incident": f"{PLUGIN}.acknowledge",
        "handle_incident_action_buttons": f"{PLUGIN}.alert",
    }


def test_the_primary_id_still_needs_the_plugin_prefix(registrar: PluginSlackRegistrar) -> None:
    with pytest.raises(ValueError, match="entry-point name"):
        registrar.register_attachment_action("alert", listener, legacy_callback_ids=("handle_incident_action_buttons",))
    with pytest.raises(ValueError, match="entry-point name"):
        registrar.register_block_action("acknowledge", listener, legacy_action_ids=("ack_incident",))


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_legacy_id_is_refused(registrar: PluginSlackRegistrar, blank: str) -> None:
    with pytest.raises(ValueError):
        registrar.register_block_action(f"{PLUGIN}.acknowledge", listener, legacy_action_ids=(blank,))


def test_a_legacy_id_repeated_in_one_registration_is_refused(registrar: PluginSlackRegistrar) -> None:
    with pytest.raises(ValueError, match="ack_incident"):
        registrar.register_block_action(f"{PLUGIN}.acknowledge", listener, legacy_action_ids=("ack_incident", "ack_incident"))


def test_an_id_taken_by_the_other_action_kind_is_refused(registrar: PluginSlackRegistrar) -> None:
    registrar.register_block_action(f"{PLUGIN}.acknowledge", listener, legacy_action_ids=("ack_incident",))

    with pytest.raises(ValueError, match="ack_incident"):
        registrar.register_attachment_action(f"{PLUGIN}.alert", listener, legacy_callback_ids=("ack_incident",))
    with pytest.raises(ValueError, match=f"{PLUGIN}.acknowledge"):
        registrar.register_attachment_action(f"{PLUGIN}.acknowledge", listener)


def test_a_refused_registration_stores_none_of_its_ids(provider: SlackPlatformProvider, registrar: PluginSlackRegistrar) -> None:
    registrar.register_block_action(f"{PLUGIN}.acknowledge", listener, legacy_action_ids=("ack_incident",))

    with pytest.raises(ValueError):
        registrar.register_attachment_action(f"{PLUGIN}.alert", listener, legacy_callback_ids=("fresh_id", "ack_incident"))

    assert provider.legacy_ids() == {"ack_incident": f"{PLUGIN}.acknowledge"}
    registrar.register_attachment_action(f"{PLUGIN}.alert", listener, legacy_callback_ids=("fresh_id",))


def test_each_legacy_id_is_logged_once_with_its_plugin(registrar: PluginSlackRegistrar) -> None:
    with capture_logs() as events:
        registrar.register_attachment_action(f"{PLUGIN}.alert", listener, legacy_callback_ids=("a_legacy", "b_legacy"))

    logged = [event for event in events if event["event"] == "slack_legacy_id_registered"]
    assert [(event["plugin"], event["legacy_id"], event["id"]) for event in logged] == [
        (PLUGIN, "a_legacy", f"{PLUGIN}.alert"),
        (PLUGIN, "b_legacy", f"{PLUGIN}.alert"),
    ]


def test_scoped_legacy_ids_are_exempt_from_the_prefix_and_listed_with_their_values(
    provider: SlackPlatformProvider, registrar: PluginSlackRegistrar
) -> None:
    registrar.register_attachment_action(
        f"{PLUGIN}.archive", listener, legacy_callback_values={"archive_channel": ("archive", "ignore")}
    )

    assert provider.legacy_callback_values() == {
        ("archive_channel", "archive"): f"{PLUGIN}.archive",
        ("archive_channel", "ignore"): f"{PLUGIN}.archive",
    }
    assert provider.legacy_ids() == {}


@pytest.mark.parametrize(
    "values",
    [
        {" ": ("archive",)},
        {"archive_channel": (" ",)},
        {"archive_channel": ()},
        {"archive_channel": "archive"},
        {"archive_channel": ("archive", "archive")},
    ],
)
def test_a_malformed_value_scope_is_refused(registrar: PluginSlackRegistrar, values: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        registrar.register_attachment_action(f"{PLUGIN}.archive", listener, legacy_callback_values=values)


def test_a_callback_id_both_unscoped_and_scoped_is_refused(registrar: PluginSlackRegistrar) -> None:
    with pytest.raises(ValueError, match="archive_channel"):
        registrar.register_attachment_action(
            f"{PLUGIN}.archive",
            listener,
            legacy_callback_ids=("archive_channel",),
            legacy_callback_values={"archive_channel": ("archive",)},
        )


def test_each_scoped_value_is_logged_once_with_its_plugin(registrar: PluginSlackRegistrar) -> None:
    with capture_logs() as events:
        registrar.register_attachment_action(
            f"{PLUGIN}.archive", listener, legacy_callback_values={"archive_channel": ("archive", "ignore")}
        )

    logged = [event for event in events if event["event"] == "slack_legacy_id_registered"]
    assert [(event["plugin"], event["legacy_id"], event["value"], event["id"]) for event in logged] == [
        (PLUGIN, "archive_channel", "archive", f"{PLUGIN}.archive"),
        (PLUGIN, "archive_channel", "ignore", f"{PLUGIN}.archive"),
    ]
