"""Access Sync singleton provider functions.

Each function here is decorated with ``@lru_cache(maxsize=1)`` to ensure a
single instance per process lifetime.  All infrastructure clients
(AWS, directory, storage) are obtained from ``infrastructure.services`` —
never instantiated directly — so bootstrap config is applied centrally.

These providers are the only place that assembles the object graph for the
access sync feature.  To substitute a dependency in tests, patch the
provider function itself (e.g. ``providers.get_access_sync_coordinator``).
"""

from functools import lru_cache
from typing import Dict, Optional

from infrastructure.events import EventDispatcher
from infrastructure.operations import OperationResult
from infrastructure.services import (
    get_aws_clients,
    get_directory_provider,
    get_storage_service,
)
from packages.access_sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access_sync.adapters.fake_platform import FakePlatformAdapter
from packages.access_sync.adapters import AccessSyncAdapter
from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    AccessSyncSettings,
    get_access_sync_config_loader,
)
from packages.access_sync.store import SyncRunRepository
from packages.access_sync.coordinator import AccessSyncCoordinator
from packages.access_sync.desired_state import DirectoryMembershipBuilder


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
def get_access_sync_adapters() -> Dict[str, AccessSyncAdapter]:
    """Create the adapter mapping from centralized pre-configured service clients.

    Infrastructure clients are obtained from infrastructure.services and come
    fully configured with all bootstrap settings (e.g., AWS_SSO_INSTANCE_ID).
    Feature configuration handles only policy definitions, not infra setup.
    """
    adapters: Dict[str, AccessSyncAdapter] = {}
    runtime_config = get_access_sync_runtime_config()

    for platform_key in runtime_config.platforms:
        if platform_key == "aws":
            aws_clients = get_aws_clients()
            adapters[platform_key] = AwsIdentityCenterAdapter(
                aws_clients=aws_clients,
            )
            continue
        if platform_key == "fake":
            adapters[platform_key] = FakePlatformAdapter()

    return adapters


@lru_cache(maxsize=1)
def get_access_sync_coordinator() -> AccessSyncCoordinator:
    """Return the singleton AccessSyncCoordinator.

    Wires together:
    - Adapter mapping from runtime config + centralized clients.
    - Policy mapping from runtime config.
    - DirectoryMembershipBuilder from infrastructure.services (IDP-agnostic).
    - SyncRunRepository backed by the storage service.
    - EventDispatcher for domain event emission.
    """
    directory = get_directory_provider()
    membership_builder = DirectoryMembershipBuilder(directory)
    repository = SyncRunRepository(storage=get_storage_service())
    runtime_config = get_access_sync_runtime_config()
    return AccessSyncCoordinator(
        adapters=get_access_sync_adapters(),
        config=runtime_config,
        membership_builder=membership_builder,
        repository=repository,
        dispatcher=EventDispatcher(),
    )
