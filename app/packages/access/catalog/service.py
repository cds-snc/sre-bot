"""Access Catalog service — discovery orchestration.

Two public methods:
    list_platforms()                       — list all configured platforms.
    list_entitlements(platform, user_email) — enumerate entitlements with
                                             membership annotation.

All I/O is read-only: runtime config reads and directory membership checks.
No state is modified here.
"""

from typing import TYPE_CHECKING, Protocol

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.catalog.domain import (
    EntitlementEntry,
    PlatformSummary,
)
from packages.access.catalog.parsers import CatalogSlugParser, FallbackCatalogSlugParser

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access.common.config import AccessRuntimeConfig

logger = structlog.get_logger()


class CatalogServicePort(Protocol):
    """Structural contract for the catalog service consumed by route handlers."""

    def list_platforms(self) -> OperationResult[list[PlatformSummary]]: ...

    def list_entitlements(
        self,
        platform: str,
        user_email: str,
    ) -> OperationResult[list[EntitlementEntry]]: ...


class CatalogService:
    """Orchestrates platform and entitlement discovery.

    Constructed once per process by ``providers.get_catalog_service``.

    Args:
        runtime_config: Access Sync runtime config; the source of platform
            policy and group naming conventions.
        directory: IDP directory provider for group discovery and membership checks.
        parsers: Mapping of platform key → ``CatalogSlugParser``.
            Platforms without an entry fall back to ``FallbackCatalogSlugParser``.
        display_names: Optional mapping of platform key → human-readable name.
    """

    def __init__(
        self,
        runtime_config: AccessRuntimeConfig,
        directory: DirectoryProvider,
        parsers: dict[str, CatalogSlugParser],
        display_names: dict[str, str] | None = None,
    ) -> None:
        self._config = runtime_config
        self._directory = directory
        self._parsers = parsers
        self._display_names = display_names or {}
        self._fallback_parser = FallbackCatalogSlugParser()
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_platforms(self) -> OperationResult[list[PlatformSummary]]:
        """Return a summary for every configured platform.

        No IDP calls are made — this is a pure config read.

        Returns:
            ``OperationResult[List[PlatformSummary]]`` ordered by platform key.
        """
        log = self.logger.bind(operation="list_platforms")
        log.info("catalog_list_platforms_started")

        summaries: list[PlatformSummary] = []
        for key in sorted(self._config.platforms.keys()):
            authn_slug = self._config.authn_group_slug(key)
            display_name = self._display_names.get(key, key)
            summaries.append(
                PlatformSummary(
                    key=key,
                    display_name=display_name,
                    authn_group_slug=authn_slug,
                )
            )

        log.info("catalog_platforms_listed", count=len(summaries))
        return OperationResult.success(data=summaries)

    def list_entitlements(
        self,
        platform: str,
        user_email: str,
    ) -> OperationResult[list[EntitlementEntry]]:
        """Enumerate all entitlements for a platform with membership annotation.

        Steps:
        1. Validate the platform key exists in runtime config.
        2. Discover IDP group slugs matching the platform prefix.
        3. For each slug: resolve mode, parse token, check membership.
        4. Return all entries, all modes included.

        Membership check failures are non-fatal: the entry is included with
        ``already_provisioned=None`` and a warning is logged.

        Args:
            platform: Normalized platform key (e.g. ``"aws"``).
            user_email: Email of the authenticated requester.

        Returns:
            ``OperationResult[List[EntitlementEntry]]`` ordered by token.
        """
        normalized = platform.strip().lower()
        log = self.logger.bind(
            operation="list_entitlements",
            platform=normalized,
            user_email=user_email,
        )
        log.info("catalog_list_entitlements_started")

        if normalized not in self._config.platforms:
            log.warning("catalog_platform_not_found")
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Platform '{normalized}' is not configured.",
                error_code="PLATFORM_NOT_FOUND",
            )

        policy = self._config.platforms[normalized]
        prefix = self._config.group_prefix(normalized)
        parser = self._parsers.get(normalized, self._fallback_parser)

        # Discover IDP groups matching the platform prefix.
        discovery_result = self._directory.list_groups(query=prefix)
        if not discovery_result.is_success or discovery_result.data is None:
            log.error(
                "catalog_group_discovery_failed",
                error=discovery_result.message,
            )
            return OperationResult.error(
                discovery_result.status,
                message=discovery_result.message,
                error_code=discovery_result.error_code or "GROUP_DISCOVERY_FAILED",
            )

        groups = discovery_result.data  # List[DirectoryGroup]
        authn_slug = self._config.authn_group_slug(normalized)

        entries: list[EntitlementEntry] = []
        requestable_count = 0
        provisioned_count = 0

        for group in sorted(groups, key=lambda g: g.group_slug):
            slug = group.group_slug.strip().lower()

            # Skip the authn lifecycle group — it's not a requestable entitlement.
            if slug == authn_slug.lower():
                continue

            # Derive the token by stripping the platform prefix.
            if not slug.startswith(prefix.lower()):
                continue
            token = slug[len(prefix) :]
            if not token:
                continue

            # Resolve effective mode from config-time overrides.
            raw_mode = policy.mode_overrides.get(token, "sync_managed")
            mode: str = raw_mode if raw_mode in ("sync_managed", "ephemeral", "deactivated") else "sync_managed"
            requestable = mode == "sync_managed"

            parsed_token = parser.parse(token)

            already_provisioned = self._check_membership(
                group_email=group.group_email,
                user_email=user_email,
                log=log,
                token=token,
            )

            entry = EntitlementEntry(
                token=token,
                group_slug=slug,
                group_email=group.group_email,
                mode=mode,  # type: ignore[arg-type]
                requestable=requestable,
                already_provisioned=already_provisioned,
                parsed_token=parsed_token,
            )
            entries.append(entry)

            if requestable:
                requestable_count += 1
            if already_provisioned:
                provisioned_count += 1

        log.info(
            "catalog_entitlements_listed",
            total=len(entries),
            requestable_count=requestable_count,
            already_provisioned_count=provisioned_count,
        )
        return OperationResult.success(data=entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_membership(
        self,
        group_email: str,
        user_email: str,
        log: object,
        token: str,
    ) -> bool | None:
        """Return membership status; None on IDP error (non-fatal)."""
        result = self._directory.check_membership(group_email, user_email)
        if not result.is_success:
            log.warning(
                "catalog_membership_check_failed",
                token=token,
                group_email=group_email,
                error=result.message,
            )
            return None
        return result.data.is_member if result.data else False
