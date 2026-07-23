"""Access common singleton provider functions.

``get_access_runtime_config`` is the single authoritative provider for the
shared access runtime config.  It is consumed by all access sub-packages
(sync, catalog, request) — they import from here, never from each other.

``get_access_settings`` (imported from ``packages.access.common.settings``) is
the provider for the unified feature settings that control all access
sub-features.  Bootstrap config (which loader source/ref) lives there under
``settings.config``.
"""

from functools import lru_cache

from infrastructure.operations import OperationResult
from packages.access.common.config import (
    AccessRuntimeConfig,
    get_access_config_loader,
)
from packages.access.common.settings import get_access_settings


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
    settings = get_access_settings()
    loader = get_access_config_loader(source=settings.config.source)
    result: OperationResult[AccessRuntimeConfig] = loader.load(ref=settings.config.ref)
    config: AccessRuntimeConfig | None = result.data
    if not result.is_success or config is None:
        raise RuntimeError(f"access_config_load_failed: {result.message}")
    return config
