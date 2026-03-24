"""Shared runtime resolution helpers for Access Sync services."""

from dataclasses import dataclass
from typing import Mapping

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.adapters import AccessSyncAdapter
from packages.access_sync.policies import PlatformPolicy


@dataclass(frozen=True)
class ResolvedPlatformContext:
    """Resolved policy and adapter for one platform key."""

    platform: str
    policy: PlatformPolicy
    adapter: AccessSyncAdapter


def resolve_platform_context(
    platform: str,
    policies: Mapping[str, PlatformPolicy],
    adapters: Mapping[str, AccessSyncAdapter],
) -> OperationResult[ResolvedPlatformContext]:
    """Resolve the policy and adapter for a platform in one place."""
    policy = policies.get(platform)
    if policy is None:
        return OperationResult.error(
            OperationStatus.NOT_FOUND,
            message=f"No policy for platform: {platform}",
            error_code="POLICY_NOT_FOUND",
        )

    adapter = adapters.get(platform)
    if adapter is None:
        return OperationResult.error(
            OperationStatus.NOT_FOUND,
            message=f"No adapter for platform: {platform}",
            error_code="ADAPTER_NOT_FOUND",
        )

    return OperationResult.success(
        data=ResolvedPlatformContext(
            platform=platform,
            policy=policy,
            adapter=adapter,
        )
    )
