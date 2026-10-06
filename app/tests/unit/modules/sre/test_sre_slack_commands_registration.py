"""Unit tests for how the legacy sre and dev modules expose their Slack commands."""

import pluggy

import modules.dev as dev_module
import modules.sre as sre_module
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE


def test_sre_and_dev_modules_contribute_no_plugin_hookimpls() -> None:
    """Registering both packages on a plugin manager adds no Slack command hookimpl.

    Their commands are wired by the hand-written legacy registration in the
    lifespan, so plugin discovery can never register them a second time.
    """
    plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)

    plugin_manager.register(sre_module)
    plugin_manager.register(dev_module)

    assert plugin_manager.hook.register_slack_commands.get_hookimpls() == []
