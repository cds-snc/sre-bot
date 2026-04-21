"""Shared access-domain config contracts."""

from packages.access.common.config.loaders import (
    AccessConfigLoader,
    BundleConfigLoader,
    EnvConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_config_loader,
    normalize_target_key,
)
from packages.access.common.config.settings import (
    AccessConfigBootstrapSettings,
    AccessRuntimeConfig,
    EntitlementMode,
    EntitlementModeOverride,
    EntitlementRule,
    PlatformPolicy,
)

__all__ = [
    # loaders
    "AccessConfigLoader",
    "BundleConfigLoader",
    "EnvConfigLoader",
    "FileJsonConfigLoader",
    "InlineJsonConfigLoader",
    "get_access_config_loader",
    "normalize_target_key",
    # settings / models
    "AccessConfigBootstrapSettings",
    "AccessRuntimeConfig",
    "EntitlementMode",
    "EntitlementModeOverride",
    "EntitlementRule",
    "PlatformPolicy",
]
