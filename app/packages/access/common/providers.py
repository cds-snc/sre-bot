"""Access common singleton provider functions.

``get_access_runtime_config`` is the single authoritative provider for the
shared access runtime config.  It is consumed by all access sub-packages
(sync, catalog, request) — they import from here, never from each other.

``get_access_config_settings`` provides the bootstrap settings that select the
loader source and ref. Each plugin's own settings are provided by that
plugin's ``providers.py``.
"""

from functools import lru_cache

from contracts.operations import OperationResult
from packages.access.common.config import (
    AccessRuntimeConfig,
    get_access_config_loader,
)
from packages.access.common.settings import AccessConfigSettings


@lru_cache(maxsize=1)
def get_access_config_settings() -> AccessConfigSettings:
    """Return the singleton bootstrap settings for the runtime config loader."""
    return AccessConfigSettings()


@lru_cache(maxsize=1)
def get_access_runtime_config() -> AccessRuntimeConfig:
    """Load typed runtime config from the source selected by bootstrap settings.

    Returns feature-level configuration (policies, per-group overrides).
    Infrastructure clients (AWS, Google Workspace, etc.) are obtained separately
    from infrastructure.configuration and come pre-configured with all bootstrap
    settings (e.g., AWS_SSO_INSTANCE_ID).

    Raises:
        RuntimeError: If the config cannot be loaded (misconfigured source or
            invalid document).
    """
    settings = get_access_config_settings()
    loader = get_access_config_loader(source=settings.source)
    result: OperationResult[AccessRuntimeConfig] = loader.load(ref=settings.ref)
    config: AccessRuntimeConfig | None = result.data
    if not result.is_success or config is None:
        raise RuntimeError(f"access_config_load_failed: {result.message}")
    return config
