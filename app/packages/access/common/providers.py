"""Access common singleton provider functions.

``get_access_runtime_config`` is the single authoritative provider for the
shared access runtime config.  It is consumed by all access sub-packages
(sync, catalog, request) — they import from here, never from each other.

``get_access_config_bootstrap_settings`` is the provider for the bootstrap
settings that control which source/ref is used to load the runtime config.
"""

from functools import lru_cache
from typing import Optional

from infrastructure.operations import OperationResult
from packages.access.common.config import (
    AccessConfigBootstrapSettings,
    AccessRuntimeConfig,
    get_access_config_loader,
)


@lru_cache(maxsize=1)
def get_access_config_bootstrap_settings() -> AccessConfigBootstrapSettings:
    """Return the singleton AccessConfigBootstrapSettings instance."""
    return AccessConfigBootstrapSettings()


@lru_cache(maxsize=1)
def get_access_runtime_config() -> AccessRuntimeConfig:
    """Load typed runtime config from the source selected by bootstrap settings.

    Returns feature-level configuration (policies, per-group overrides).
    Infrastructure clients (AWS, Google Workspace, etc.) are obtained separately
    from infrastructure.services and come pre-configured with all bootstrap
    settings (e.g., AWS_SSO_INSTANCE_ID).

    Raises:
        RuntimeError: If the config cannot be loaded (misconfigured source or
            invalid document).
    """
    settings = get_access_config_bootstrap_settings()
    loader = get_access_config_loader(source=settings.config_source)
    result: OperationResult[AccessRuntimeConfig] = loader.load(ref=settings.config_ref)
    config: Optional[AccessRuntimeConfig] = result.data
    if not result.is_success or config is None:
        raise RuntimeError(f"access_config_load_failed: {result.message}")
    return config
