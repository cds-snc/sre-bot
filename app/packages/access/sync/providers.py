import functools

from infrastructure.clients.aws import get_aws_clients
from infrastructure.directory import get_directory_provider
from infrastructure.events import get_event_dispatcher
from infrastructure.storage import get_storage_service
from packages.access.common.providers import get_access_runtime_config
from packages.access.common.settings import AccessSyncSettings, get_access_settings
from packages.access.sync.adapters import AccessSyncAdapter
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.sync.adapters.fake_platform import FakePlatformAdapter
from packages.access.sync.application import AccessSyncApplicationService
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.store import SyncRunRepository


def get_access_sync_settings() -> AccessSyncSettings:
    """Return the sync settings slice from the unified access settings."""
    return get_access_settings().sync


@functools.lru_cache(maxsize=1)
def get_access_sync_adapters() -> dict[str, AccessSyncAdapter]:
    """Provide a map of available platform adapters."""
    config = get_access_runtime_config()
    adapters: dict[str, AccessSyncAdapter] = {}

    for platform_name, policy in config.platforms.items():
        if policy.adapter_type == "aws_identity_center":
            adapters[platform_name] = AwsIdentityCenterAdapter(get_aws_clients())
        elif policy.adapter_type == "fake":
            adapters[platform_name] = FakePlatformAdapter()
        else:
            raise ValueError(f"unknown adapter_type '{policy.adapter_type}' for platform '{platform_name}'")

    return adapters


@functools.lru_cache(maxsize=1)
def get_sync_run_repository() -> SyncRunRepository:
    """Return the singleton SyncRunRepository instance."""
    return SyncRunRepository(storage=get_storage_service())


@functools.lru_cache(maxsize=1)
def get_access_sync_coordinator() -> AccessSyncApplicationService:
    """Return the singleton AccessSyncApplicationService instance."""
    return AccessSyncApplicationService(
        adapters=get_access_sync_adapters(),
        config=get_access_runtime_config(),
        membership_builder=DirectoryMembershipBuilder(directory=get_directory_provider()),
        repository=get_sync_run_repository(),
        dispatcher=get_event_dispatcher(),
    )
