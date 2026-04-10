"""Access Sync config sub-package.

Re-exports all public symbols from settings.py and loaders.py so that existing
``from packages.access.sync.config import ...`` statements continue to work
without modification.
"""

from packages.access.sync.config.settings import (
    AccessSyncRuntimeConfig,
    AccessSyncSettings,
    EntitlementModeOverride,
)
from packages.access.sync.config.loaders import (
    AccessSyncConfigLoader,
    BundleConfigLoader,
    EnvConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_sync_config_loader,
    normalize_target_key,
)

__all__ = [
    # settings
    "AccessSyncSettings",
    "AccessSyncRuntimeConfig",
    "EntitlementModeOverride",
    # loaders
    "AccessSyncConfigLoader",
    "BundleConfigLoader",
    "EnvConfigLoader",
    "FileJsonConfigLoader",
    "InlineJsonConfigLoader",
    "get_access_sync_config_loader",
    "normalize_target_key",
]
