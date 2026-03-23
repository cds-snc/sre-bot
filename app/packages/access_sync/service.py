"""Access Sync service facade.

Thin facade: validates prerequisites, routes to UserSyncService (on-demand)
or PlatformSyncService (batch), and normalises the result.
Feature flag enforcement is at the route boundary (routes.py).
"""

from typing import TYPE_CHECKING, Union

import structlog

from infrastructure.operations import OperationResult
from packages.access_sync.schemas import PlatformSyncRequest, UserSyncRequest

if TYPE_CHECKING:
    from packages.access_sync.platform_sync.service import PlatformSyncService
    from packages.access_sync.user_sync.service import UserSyncService

logger = structlog.get_logger()


class AccessSyncService:
    """Access Sync facade.

    Routes sync requests to UserSyncService (on-demand single-user) or
    PlatformSyncService (batch group-driven). Does not contain business logic.

    Args:
        user_sync_service: Handles on-demand single-user convergence.
        platform_sync_service: Handles batch platform-wide convergence.
    """

    def __init__(
        self,
        user_sync_service: "UserSyncService",
        platform_sync_service: "PlatformSyncService",
    ) -> None:
        self._user_sync = user_sync_service
        self._platform_sync = platform_sync_service

    def sync(
        self,
        request: Union[UserSyncRequest, PlatformSyncRequest],
    ) -> OperationResult:
        """Route request to the correct sub-service.

        Returns:
            OperationResult[SyncOutcome] for UserSyncRequest.
            OperationResult[ReconciliationOutcome] for PlatformSyncRequest.
        """
        if isinstance(request, UserSyncRequest):
            return self._user_sync.sync_user(
                user_email=request.user_email,
                platform=request.platform,
                dry_run=request.dry_run,
                request_id=request.request_id or "",
            )
        return self._platform_sync.sync_platform(
            platform=request.platform,
            dry_run=request.dry_run,
        )
