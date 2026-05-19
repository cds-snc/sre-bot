"""Plugin managers and utilities."""

import pluggy

from infrastructure.plugins.manager import (
    get_plugin_manager,
    discover_and_init_features,
    collect_feature_i18n_resources,
    register_feature_integrations,
)

# Singleton hookimpl marker for entire application
hookimpl = pluggy.HookimplMarker("sre_bot")

__all__ = [
    "hookimpl",
    "get_plugin_manager",
    "discover_and_init_features",
    "collect_feature_i18n_resources",
    "register_feature_integrations",
]
