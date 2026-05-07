"""Unit tests for PR-18 hookspec renames (ADR-0089 Standard 3).

Verifies that:
  - New interaction hookspec names exist on features module and plugin manager.
  - register_event_handlers exists (ADR-0083 S3).
  - Old *_commands names are removed.
"""

import pluggy
import pytest

from infrastructure.hookspecs import features


@pytest.mark.unit
def test_register_slack_interactions_hookspec_exists() -> None:
    assert hasattr(features, "register_slack_interactions")


@pytest.mark.unit
def test_register_teams_interactions_hookspec_exists() -> None:
    assert hasattr(features, "register_teams_interactions")


@pytest.mark.unit
def test_register_discord_interactions_hookspec_exists() -> None:
    assert hasattr(features, "register_discord_interactions")


@pytest.mark.unit
def test_register_event_handlers_hookspec_exists() -> None:
    assert hasattr(features, "register_event_handlers")


@pytest.mark.unit
def test_old_slack_commands_hookspec_removed() -> None:
    assert not hasattr(features, "register_slack_commands")


@pytest.mark.unit
def test_old_teams_commands_hookspec_removed() -> None:
    assert not hasattr(features, "register_teams_commands")


@pytest.mark.unit
def test_old_discord_commands_hookspec_removed() -> None:
    assert not hasattr(features, "register_discord_commands")


@pytest.mark.unit
def test_plugin_manager_exposes_register_slack_interactions() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)

    hook = getattr(pm.hook, "register_slack_interactions", None)
    assert hook is not None
    assert callable(hook)


@pytest.mark.unit
def test_plugin_manager_exposes_register_teams_interactions() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)

    hook = getattr(pm.hook, "register_teams_interactions", None)
    assert hook is not None
    assert callable(hook)


@pytest.mark.unit
def test_plugin_manager_exposes_register_discord_interactions() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)

    hook = getattr(pm.hook, "register_discord_interactions", None)
    assert hook is not None
    assert callable(hook)


@pytest.mark.unit
def test_plugin_manager_does_not_expose_old_slack_commands() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)

    assert not hasattr(pm.hook, "register_slack_commands")


@pytest.mark.unit
def test_plugin_manager_does_not_expose_old_teams_commands() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)

    assert not hasattr(pm.hook, "register_teams_commands")
