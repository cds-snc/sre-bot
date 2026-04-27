"""Unit tests for infrastructure.hookspecs.features contract surface."""

import pluggy
import pytest

from infrastructure.hookspecs import features


@pytest.mark.unit
def test_features_hookspec_namespace_defines_register_background_job() -> None:
    assert hasattr(features, "register_background_job")


@pytest.mark.unit
def test_plugin_manager_exposes_register_background_job_hook() -> None:
    plugin_manager = pluggy.PluginManager("sre_bot")
    plugin_manager.add_hookspecs(features)

    hook = getattr(plugin_manager.hook, "register_background_job", None)
    assert hook is not None
    assert callable(hook)
