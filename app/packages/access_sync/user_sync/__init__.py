"""Access Sync user_sync sub-package.

UserSyncService owns on-demand, single-user convergence logic:
  - Resolves authn + entitlement group tokens from the IDP (O(groups) calls).
  - Plans actions via PolicyEngine and dispatches to the platform adapter.
  - sync_user_from_context() accepts pre-fetched MembershipContext from
    PlatformSyncService to eliminate redundant IDP calls in batch runs.

Use get_user_sync_service() from packages.access_sync.providers
to obtain the singleton instance wired with all infrastructure dependencies.
"""

from packages.access_sync.user_sync.service import UserSyncService

__all__ = ["UserSyncService"]
