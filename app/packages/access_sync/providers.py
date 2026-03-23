"""Access Sync singleton provider functions.

Uses @lru_cache to create one instance of each service per process.
All clients are obtained from infrastructure.services — never instantiated locally.
"""

from functools import lru_cache
from typing import Optional

from infrastructure.events import EventDispatcher
from infrastructure.operations import OperationResult
from infrastructure.services import (
    get_aws_clients,
    get_directory_provider,
    get_storage_service,
)
from packages.access_sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    AccessSyncSettings,
    get_access_sync_config_loader,
)
from packages.access_sync.platform_sync.service import PlatformSyncService
from packages.access_sync.policies import PolicyRegistry
from packages.access_sync.registry import AccessSyncRegistry
from packages.access_sync.service import AccessSyncService
from packages.access_sync.store import SyncRunRepository
from packages.access_sync.user_sync.service import UserSyncService


@lru_cache(maxsize=1)
def get_access_sync_settings() -> AccessSyncSettings:
    """Return the singleton AccessSyncSettings instance."""
    return AccessSyncSettings()


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
    settings = get_access_sync_settings()
    loader = get_access_sync_config_loader(
        source=settings.config_source,
    )
    result: OperationResult[AccessSyncRuntimeConfig] = loader.load(
        ref=settings.config_ref,
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
def get_user_sync_service() -> UserSyncService:
    """Return the singleton UserSyncService for on-demand single-user sync.

    Wires together:
    - Adapter registry from runtime config + centralized clients.
    - PolicyRegistry from runtime config.
    - DirectoryProvider from infrastructure.services (IDP-agnostic).
    - SyncRunRepository backed by the storage service.
    - EventDispatcher for domain event emission.
    """
    runtime_config = get_access_sync_runtime_config()
    registry = get_access_sync_registry()
    policies = PolicyRegistry(policies=runtime_config.policies)
    directory = get_directory_provider()
    repository = SyncRunRepository(storage=get_storage_service())
    return UserSyncService(
        registry=registry,
        policies=policies,
        directory=directory,
        repository=repository,
        dispatcher=EventDispatcher(),
    )


@lru_cache(maxsize=1)
def get_platform_sync_service() -> PlatformSyncService:
    """Return the singleton PlatformSyncService for batch platform-wide sync.

    Batch-reads IDP group membership once per platform sync run (O(groups))
    and delegates per-user convergence to UserSyncService.sync_user_from_context.
    """
    runtime_config = get_access_sync_runtime_config()
    policies = PolicyRegistry(policies=runtime_config.policies)
    return PlatformSyncService(
        sync_service=get_user_sync_service(),
        registry=get_access_sync_registry(),
        policies=policies,
        directory=get_directory_provider(),
        dispatcher=EventDispatcher(),
    )


@lru_cache(maxsize=1)
def get_access_sync_service() -> AccessSyncService:
    """Return the singleton AccessSyncService facade.

    Wraps UserSyncService and PlatformSyncService behind a unified
    sync(request) interface keyed on the request discriminator.
    """
    return AccessSyncService(
        user_sync_service=get_user_sync_service(),
        platform_sync_service=get_platform_sync_service(),
    )
