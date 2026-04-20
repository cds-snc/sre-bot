"""Access Requests singleton provider functions.

Each function is decorated with ``@lru_cache(maxsize=1)`` to ensure a single
instance per process lifetime.

To substitute a dependency in tests, patch the provider function itself at
module scope — never bypass providers by instantiating services directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.services import (
    get_directory_provider,
    get_event_dispatcher,
    get_storage_service,
)
from packages.access.request.service import AccessRequestService
from packages.access.request.store import AccessRequestRepository
from packages.access.sync.providers import get_access_runtime_config


class AccessRequestSettings(BaseSettings):
    """Bootstrap settings for Access Requests.

    All settings default to safe/off values so the feature is opt-in.

    Environment Variables:
        ACCESS_REQUESTS_ENABLED: Master on/off switch. Default: false.
        ACCESS_REQUESTS_MANAGER_GROUP_SLUG: IDP group whose members may submit
            delegated requests. Default: sg-managers.
        ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG: Org-level approver fallback
            group slug. Default: sg-org-admins.
        ACCESS_REQUESTS_MIN_APPROVER_COUNT: Minimum affirmative decisions to
            approve a request. Default: 1.
        ACCESS_REQUESTS_REQUEST_TTL_HOURS: Hours before a pending request
            expires. Default: 72.
    """

    enabled: bool = Field(default=False, alias="ACCESS_REQUESTS_ENABLED")
    manager_group_slug: str = Field(
        default="sg-managers", alias="ACCESS_REQUESTS_MANAGER_GROUP_SLUG"
    )
    fallback_approver_slug: str = Field(
        default="sg-org-admins", alias="ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG"
    )
    min_approver_count: int = Field(
        default=1, alias="ACCESS_REQUESTS_MIN_APPROVER_COUNT"
    )
    request_ttl_hours: int = Field(
        default=72, alias="ACCESS_REQUESTS_REQUEST_TTL_HOURS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_access_request_settings() -> AccessRequestSettings:
    """Return the singleton AccessRequestSettings instance."""
    return AccessRequestSettings()


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
