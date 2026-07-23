"""Plugin managers and utilities."""

import pluggy

from infrastructure.plugins.manager import (
    auto_discover_plugins,
    collect_feature_i18n_resources,
    get_plugin_manager,
    register_feature_integrations,
)

# Singleton hookimpl marker for entire application
hookimpl = pluggy.HookimplMarker("sre_bot")

__all__ = [
    "hookimpl",
    "get_plugin_manager",
    "collect_feature_i18n_resources",
    "register_feature_integrations",
    "auto_discover_plugins",
]
