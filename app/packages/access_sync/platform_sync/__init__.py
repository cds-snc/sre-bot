"""Access Sync platform_sync sub-package.

PlatformSyncService owns batch, group-driven convergence for all users
on a platform:
  - Batch IDP state collection: O(groups) directory calls total.
  - Orphan detection: users present on platform but no longer in IDP.
  - Per-user convergence via UserSyncService.sync_user_from_context
    (pre-fetched MembershipContext — zero additional IDP calls per user).
  - PLATFORM_SYNC_STARTED / PLATFORM_SYNC_COMPLETED domain event emission.

Use get_platform_sync_service() from packages.access_sync.providers
to obtain the singleton instance wired with all infrastructure dependencies.
"""

from packages.access_sync.platform_sync.service import PlatformSyncService

__all__ = ["PlatformSyncService"]
