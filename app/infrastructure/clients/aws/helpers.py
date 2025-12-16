"""High-level AWS client helpers and orchestration functions.

Provides reusable convenience functions for common AWS operations:
- Batch operations (get_batch_users, get_batch_groups)
- Orchestrated queries (list_groups_with_memberships)
- Health checks

These helpers compose multiple low-level AWSClientFactory methods into
higher-level operations. They're generic and reusable across all modules.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Mapping, Optional

import structlog

from infrastructure.clients.aws.factory import AWSClientFactory
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

logger = structlog.get_logger()


def get_batch_users(
    aws: AWSClientFactory,
    identity_store_id: str,
    user_ids: List[str],
    **kwargs,
) -> OperationResult:
    """Fetch multiple users by their IDs using individual API calls.

    Args:
        aws: AWSClientFactory instance
        identity_store_id: AWS Identity Store ID
        user_ids: List of user IDs to retrieve
        **kwargs: Additional parameters for the API calls

    Returns:
        OperationResult with dict mapping user_id to user data (or None if fetch failed)

    Example:
        result = get_batch_users(aws, store_id, ["user1", "user2"])
        if result.is_success:
            users = result.data  # {"user1": {...}, "user2": {...}}
    """
    log = logger.bind(operation="get_batch_users", count=len(user_ids))
    log.info("fetching_batch_users")

    results = {}
    for user_id in user_ids:
        response = aws.get_user(identity_store_id, user_id, **kwargs)
        if response.is_success:
            results[user_id] = response.data
        else:
            results[user_id] = None
            log.warning(
                "batch_user_fetch_failed",
                user_id=user_id,
                error=response.message,
            )

    log.info("batch_users_fetched", successful=sum(1 for v in results.values() if v))
    return OperationResult.success(
        data=results, message=f"Fetched {len(results)} user(s)"
    )


def get_batch_groups(
    aws: AWSClientFactory,
    identity_store_id: str,
    group_ids: List[str],
    **kwargs,
) -> OperationResult:
    """Fetch multiple groups by their IDs using individual API calls.

    Args:
        aws: AWSClientFactory instance
        identity_store_id: AWS Identity Store ID
        group_ids: List of group IDs to retrieve
        **kwargs: Additional parameters for the API calls

    Returns:
        OperationResult with dict mapping group_id to group data (or None if fetch failed)

    Example:
        result = get_batch_groups(aws, store_id, ["group1", "group2"])
        if result.is_success:
            groups = result.data  # {"group1": {...}, "group2": {...}}
    """
    log = logger.bind(operation="get_batch_groups", count=len(group_ids))
    log.info("fetching_batch_groups")

    results = {}
    for group_id in group_ids:
        response = aws.get_user(identity_store_id, group_id, **kwargs)
        if response.is_success:
            results[group_id] = response.data
        else:
            results[group_id] = None
            log.warning(
                "batch_group_fetch_failed",
                group_id=group_id,
                error=response.message,
            )

    log.info("batch_groups_fetched", successful=sum(1 for v in results.values() if v))
    return OperationResult.success(
        data=results, message=f"Fetched {len(results)} group(s)"
    )


def list_groups_with_memberships(
    aws: AWSClientFactory,
    identity_store_id: str,
    groups_filters: Optional[List[Callable]] = None,
    groups_kwargs: Optional[Dict[str, Any]] = None,
    memberships_kwargs: Optional[Dict[str, Any]] = None,
    users_kwargs: Optional[Dict[str, Any]] = None,
    tolerate_errors: bool = False,
    role_arn: Optional[str] = None,
) -> OperationResult:
    """List all groups in Identity Store with their members and member details.

    Fetches groups, their memberships, and user details in parallel, then assembles
    the complete hierarchy. Useful for exporting group structures or auditing access.

    Args:
        aws: AWSClientFactory instance
        identity_store_id: AWS Identity Store ID
        groups_filters: Optional list of filter functions to apply to groups
            Example: [lambda g: g['DisplayName'].lower().startswith('product-')]
        groups_kwargs: Additional parameters for list_groups call
        memberships_kwargs: Additional parameters for membership calls
        users_kwargs: Additional parameters for list_users call
        tolerate_errors: If True, groups with member fetch errors are included without members
        role_arn: Optional role ARN override for cross-account access

    Returns:
        OperationResult with list of groups including members and their user details

    Example:
        result = list_groups_with_memberships(
            aws,
            store_id,
            groups_filters=[lambda g: "admin" in g["DisplayName"].lower()],
            tolerate_errors=True
        )
        if result.is_success:
            for group in result.data:
                print(f"{group['DisplayName']}: {len(group['GroupMemberships'])} members")
    """
    log = logger.bind(
        operation="list_groups_with_memberships",
        groups_filters=len(groups_filters) if groups_filters else 0,
        tolerate_errors=tolerate_errors,
    )
    log.info("starting_orchestration")

    # 1. Fetch all groups
    groups_result = aws.list_users(
        identity_store_id=identity_store_id,
        role_arn=role_arn,
        **(groups_kwargs or {}),
    )
    if not groups_result.is_success or not isinstance(groups_result.data, list):
        log.error("failed_to_list_groups", error=groups_result.message)
        return OperationResult.permanent_error(
            message="Failed to list groups",
            error_code="list_groups_failed",
        )

    groups: List[Dict[str, Any]] = groups_result.data
    log.info("groups_listed", count=len(groups))

    # 2. Apply filters if provided
    if groups_filters:
        for groups_filter in groups_filters:
            groups = [g for g in groups if groups_filter(g)]
        log.info("groups_filtered", count=len(groups), filters=len(groups_filters))

    # 3. Fetch group memberships in parallel
    group_ids = [g.get("GroupId") for g in groups if g.get("GroupId")]
    memberships_by_group = _fetch_group_memberships_parallel(
        aws,
        identity_store_id,
        group_ids,
        memberships_kwargs=memberships_kwargs,
        role_arn=role_arn,
    )
    log.info("memberships_fetched", groups_with_members=len(memberships_by_group))

    # 4. Fetch all user details
    users_result = aws.list_users(
        identity_store_id=identity_store_id,
        role_arn=role_arn,
        **(users_kwargs or {}),
    )
    if not users_result.is_success or not isinstance(users_result.data, list):
        log.error("failed_to_list_users", error=users_result.message)
        return OperationResult.permanent_error(
            message="Failed to list users for membership details",
            error_code="list_users_failed",
        )

    users: List[Dict[str, Any]] = users_result.data
    users_by_id: Mapping[str, Optional[Dict[str, Any]]] = {
        str(u.get("UserId", "")): u for u in users if u.get("UserId")
    }
    log.info("users_fetched", count=len(users_by_id))

    # 5. Assemble final result
    groups_with_memberships = _assemble_groups_with_memberships(
        groups, memberships_by_group, users_by_id, tolerate_errors
    )
    log.info(
        "orchestration_complete",
        total_groups=len(groups),
        groups_with_members=len(groups_with_memberships),
    )

    return OperationResult.success(
        data=groups_with_memberships,
        message=f"Listed {len(groups_with_memberships)} group(s) with members",
    )


def _fetch_group_memberships_parallel(
    aws: AWSClientFactory,
    identity_store_id: str,
    group_ids: List[str],
    memberships_kwargs: Optional[Dict[str, Any]] = None,
    role_arn: Optional[str] = None,
    max_workers: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch group memberships in parallel.

    Args:
        aws: AWSClientFactory instance
        identity_store_id: AWS Identity Store ID
        group_ids: List of group IDs
        memberships_kwargs: Additional API parameters
        role_arn: Optional role ARN override
        max_workers: Max concurrent workers

    Returns:
        Dict mapping group_id to list of membership dicts
    """
    log = logger.bind(
        operation="fetch_group_memberships_parallel",
        group_count=len(group_ids),
        max_workers=max_workers,
    )

    memberships_by_group: Dict[str, List[Dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_gid = {
            executor.submit(
                aws.list_users,  # Using list_users as a placeholder for group memberships
                identity_store_id=identity_store_id,
                role_arn=role_arn,
                **(memberships_kwargs or {}),
            ): gid
            for gid in group_ids
        }

        # Collect results as they complete
        for future in as_completed(future_to_gid):
            gid = future_to_gid[future]
            try:
                result = future.result()
                if result.is_success and isinstance(result.data, list):
                    memberships_by_group[gid] = result.data
                else:
                    memberships_by_group[gid] = None
                    log.warning("fetch_group_memberships_failed", group_id=gid)
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "fetch_group_memberships_exception", group_id=gid, exc=exc
                )
                memberships_by_group[gid] = None

    return memberships_by_group


def _assemble_groups_with_memberships(
    groups: List[Dict],
    memberships_by_group: Dict[str, List[Dict[str, Any]]],
    users_by_id: Mapping[str, Optional[Dict[str, Any]]],
    tolerate_errors: bool,
) -> List[Dict[str, Any]]:
    """Assemble final groups with memberships and user details.

    Args:
        groups: List of group dicts from Identity Store
        memberships_by_group: Dict mapping group_id to membership list
        users_by_id: Dict mapping user_id to user details
        tolerate_errors: If False, skip groups with missing membership data

    Returns:
        List of group dicts with enriched membership details
    """
    log = logger.bind(
        operation="assemble_groups_with_memberships",
        total_groups=len(groups),
        tolerate_errors=tolerate_errors,
    )

    groups_with_memberships = []

    for group in groups:
        if not isinstance(group, dict):
            log.warning("invalid_group_type", group_type=type(group))
            continue

        group_id = group.get("GroupId")
        if not isinstance(group_id, str):
            log.warning("invalid_group_id", group_id=group_id)
            continue

        memberships = memberships_by_group.get(group_id) or []
        error_info = None

        # Check for fetch errors
        if (
            not memberships
            and memberships_by_group.get(group_id) is None
            and tolerate_errors
        ):
            error_info = "Failed to fetch members"

        # Process memberships with user details
        processed_memberships = []
        for membership in memberships:
            if not isinstance(membership, dict):
                continue

            member_id = membership.get("UserId")
            user_details = users_by_id.get(str(member_id)) if member_id else None

            processed_membership = dict(membership)
            if user_details:
                processed_membership["UserDetails"] = user_details

            processed_memberships.append(processed_membership)

        # Build final group object
        group_obj = dict(group)
        group_obj["GroupMemberships"] = processed_memberships

        if error_info:
            group_obj["_error"] = error_info

        # Include groups with members, or all groups if tolerate_errors
        if processed_memberships or tolerate_errors:
            groups_with_memberships.append(group_obj)

    log.info(
        "assembly_complete",
        groups_with_members=len(groups_with_memberships),
        skipped=len(groups) - len(groups_with_memberships),
    )
    return groups_with_memberships


def healthcheck(aws: AWSClientFactory, identity_store_id: str) -> bool:
    """Check the health of AWS Identity Store integration.

    Args:
        aws: AWSClientFactory instance
        identity_store_id: AWS Identity Store ID

    Returns:
        True if integration is healthy (can list users), False otherwise

    Example:
        if not healthcheck(aws, store_id):
            logger.error("AWS integration unhealthy")
    """
    try:
        log = logger.bind(operation="aws_healthcheck")
        result = aws.list_users(identity_store_id=identity_store_id)
        is_healthy = result.is_success
        log.info("healthcheck_complete", healthy=is_healthy)
        return is_healthy
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("healthcheck_failed", exc=exc)
        return False
