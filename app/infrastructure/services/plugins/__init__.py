"""Plugin managers and utilities."""

import pluggy

from infrastructure.services.plugins.platforms import (
    get_platform_plugin_manager,
    discover_and_register_platforms,
)

# Singleton hookimpl marker for entire application
hookimpl = pluggy.HookimplMarker("sre_bot")

__all__ = [
    "hookimpl",
    "get_platform_plugin_manager",
    "discover_and_register_platforms",
]
