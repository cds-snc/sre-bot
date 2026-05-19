"""Access Requests singleton provider functions.

Each function is decorated with ``@lru_cache(maxsize=1)`` to ensure a single
instance per process lifetime.

To substitute a dependency in tests, patch the provider function itself at
module scope — never bypass providers by instantiating services directly.
"""

from functools import lru_cache

from infrastructure.services import (
    get_event_dispatcher,
)
from infrastructure.directory import get_directory_provider
from infrastructure.storage import get_storage_service
from packages.access.request.service import AccessRequestService
from packages.access.request.store import AccessRequestRepository
from packages.access.common.providers import get_access_runtime_config
from packages.access.common.settings import AccessRequestsSettings, get_access_settings


def get_access_request_settings() -> AccessRequestsSettings:
    """Return the requests settings slice from the unified access settings."""
    return get_access_settings().requests


@lru_cache(maxsize=1)
def get_access_request_repository() -> AccessRequestRepository:
    """Return the singleton AccessRequestRepository instance."""
    return AccessRequestRepository(storage=get_storage_service())


@lru_cache(maxsize=1)
def get_access_request_service() -> AccessRequestService:
    """Return the singleton AccessRequestService instance.

    Wires repository, directory provider, runtime config, dispatcher, and
    feature settings into a single fully-assembled service instance.
    """
    settings = get_access_request_settings()
    return AccessRequestService(
        repository=get_access_request_repository(),
        directory=get_directory_provider(),
        runtime_config=get_access_runtime_config(),
        dispatcher=get_event_dispatcher(),
        fallback_approver_slug=settings.fallback_approver_slug,
        min_approver_count=settings.min_approver_count,
    )
