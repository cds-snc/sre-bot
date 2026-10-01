"""Plugin managers and utilities."""

from infrastructure.plugins.manager import (
    auto_discover_plugins,
    collect_feature_i18n_resources,
    get_plugin_manager,
    register_feature_integrations,
)

__all__ = [
    "get_plugin_manager",
    "collect_feature_i18n_resources",
    "register_feature_integrations",
    "auto_discover_plugins",
]
