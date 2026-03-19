"""Access Sync singleton provider functions.

Uses @lru_cache to create one instance of each expensive dependency per process.
All clients are obtained from infrastructure.services — never instantiated locally.
"""

from functools import lru_cache
from typing import Optional

from infrastructure.operations import OperationResult
from infrastructure.services import (
    get_aws_clients,
    get_directory_provider,
    get_settings,
)
from packages.access_sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    get_access_sync_config_loader,
)
from packages.access_sync.policies import PolicyRegistry
from packages.access_sync.registry import AccessSyncRegistry
from packages.access_sync.service import AccessSyncService
from packages.access_sync.store import InMemorySyncRunStore


@lru_cache(maxsize=1)
def get_access_sync_runtime_config() -> AccessSyncRuntimeConfig:
    """Load typed runtime config from the source selected by bootstrap settings.

    Returns feature-level configuration (policies, per-group overrides).
    Infrastructure clients (AWS, Google Workspace, etc.) are obtained separately
    from infrastructure.services and come pre-configured with all bootstrap
    settings (e.g., AWS_SSO_INSTANCE_ID).

    Raises:
        RuntimeError: If the config cannot be loaded (misconfigured source or
            invalid document).
    """
    settings = get_settings()
    loader = get_access_sync_config_loader(
        source=settings.access_sync.config_source,
    )
    result: OperationResult[AccessSyncRuntimeConfig] = loader.load(
        ref=settings.access_sync.config_ref,
    )
    config: Optional[AccessSyncRuntimeConfig] = result.data
    if not result.is_success or config is None:
        raise RuntimeError(f"access_sync_config_load_failed: {result.message}")
    return config


@lru_cache(maxsize=1)
def get_access_sync_registry() -> AccessSyncRegistry:
    """Create the adapter registry from centralized pre-configured service clients.

    Infrastructure clients are obtained from infrastructure.services and come
    fully configured with all bootstrap settings (e.g., AWS_SSO_INSTANCE_ID).
    Feature configuration handles only policy definitions, not infra setup.
    """
    adapters = {}

    aws_clients = get_aws_clients()
    adapters["aws"] = AwsIdentityCenterAdapter(aws_clients=aws_clients)

    return AccessSyncRegistry(adapters=adapters)


@lru_cache(maxsize=1)
def get_access_sync_service() -> AccessSyncService:
    """Return the singleton AccessSyncService.

    Wires together:
    - Adapter registry from runtime config + centralized clients.
    - PolicyRegistry from runtime config.
    - DirectoryProvider from infrastructure.services (IDP-agnostic).
    - InMemorySyncRunStore for v1 (DynamoDB backend is a future milestone).
    """
    runtime_config = get_access_sync_runtime_config()
    registry = get_access_sync_registry()
    policies = PolicyRegistry(policies=runtime_config.policies)
    directory = get_directory_provider()
    store = InMemorySyncRunStore()
    return AccessSyncService(
        registry=registry,
        policies=policies,
        directory=directory,
        store=store,
    )
