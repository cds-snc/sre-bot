"""Unit tests for agent-specific hookspecs."""

import inspect

import pluggy
import pytest

from infrastructure.hookspecs import features

pytestmark = pytest.mark.unit


def test_register_slack_agent_interactions_hookspec_exists() -> None:
    plugin_manager = pluggy.PluginManager("sre_bot")
    plugin_manager.add_hookspecs(features)

    hook = getattr(plugin_manager.hook, "register_slack_agent_interactions", None)
    assert hook is not None
    assert callable(hook)


def test_slack_agent_hookspec_parameter_is_slack_service() -> None:
    signature = inspect.signature(features.register_slack_agent_interactions)

    assert "provider" in signature.parameters
    assert signature.parameters["provider"].annotation == "SlackBot"


def test_legacy_hookspecs_unchanged() -> None:
    assert hasattr(features, "register_slack_commands")
