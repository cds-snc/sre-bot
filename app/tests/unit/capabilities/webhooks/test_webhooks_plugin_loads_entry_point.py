"""Unit tests that the capability is installed as a plugin and stays inert.

The entry point is read from the installed distribution metadata, as boot reads it; the
plugin module is checked for the hookimpls it defines.
"""

import importlib.metadata

import pytest

from capabilities.webhooks import plugin
from contracts.plugins.namespace import PLUGIN_NAMESPACE

pytestmark = pytest.mark.unit


def test_the_entry_point_names_the_plugin_module() -> None:
    (entry_point,) = (entry for entry in importlib.metadata.entry_points(group=PLUGIN_NAMESPACE) if entry.name == "webhooks")

    assert entry_point.value == "capabilities.webhooks.plugin"
    assert entry_point.load() is plugin


def test_the_plugin_registers_no_route_and_requires_nothing() -> None:
    """The capability is dark: it contributes content kinds only."""
    assert plugin.register_requirements() == []
    assert not hasattr(plugin, "register_routes")
    assert not hasattr(plugin, "register_slack_commands")
