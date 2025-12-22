"""Identity Store client for AWS operations.

Provides type-safe access to AWS Identity Store operations (list_users, describe_user, create_user, etc.)
with consistent error handling and OperationResult return types.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Mapping, Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class IdentityStoreClient:
    """Client for AWS Identity Store operations.

    All methods return OperationResult for consistent error handling and
    downstream processing.

    Args:
        session_provider: SessionProvider instance for credential/config management
        default_identity_store_id: Default Identity Store ID for this client
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_identity_store_id: Optional[str] = None,
    ) -> None:
        self._session_provider = session_provider
        self._service_name = "identitystore"
        self._default_identity_store_id = default_identity_store_id
        self._logger = logger.bind(component="identity_store_client")

    def create_group_membership(
        self,
        GroupId: str,
        MemberId: Dict[str, str],
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Create a group membership in Identity Store.

        Args:
            GroupId: ID of the group
            MemberId: Dict with 'UserId' key for the member
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:
            OperationResult with membership details or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "create_group_membership",
            IdentityStoreId=store_id,
            GroupId=GroupId,
            MemberId=MemberId,
            **client_kwargs,
            **kwargs,
        )

    def create_user(
        self,
        UserName: str,
        DisplayName: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Create a new user in Identity Store.

        Args:
            UserName: Username for the new user
            DisplayName: Display name for the user
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with created user details or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "create_user",
            IdentityStoreId=store_id,
            UserName=UserName,
            DisplayName=DisplayName,
            **client_kwargs,
            **kwargs,
        )

    def delete_group_membership(
        self,
        membership_id: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Delete a group membership from Identity Store.

        Args:
            membership_id: ID of the membership to delete
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:
            OperationResult with status
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "delete_group_membership",
            IdentityStoreId=store_id,
            MembershipId=membership_id,
            **client_kwargs,
            **kwargs,
        )

    def delete_user(
        self,
        user_id: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Delete a user from Identity Store.

        Args:
            user_id: User ID to delete
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with status or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "delete_user",
            IdentityStoreId=store_id,
            UserId=user_id,
            **client_kwargs,
            **kwargs,
        )

    def describe_group(
        self,
        group_id: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Describe a group from Identity Store.

        Args:
            group_id: Group ID to retrieve
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:
            OperationResult with group details or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "describe_group",
            IdentityStoreId=store_id,
            GroupId=group_id,
            **client_kwargs,
            **kwargs,
        )

    def describe_group_by_name(
        self,
        group_name: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Describe a group from Identity Store by group name.
        Args:
            group_name: Group name to retrieve
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:

            OperationResult with group details or error
        """
        group_id_result = self.get_group_id_by_group_name(
            group_name,
            identity_store_id=identity_store_id,
            role_arn=role_arn,
            **kwargs,
        )
        if not group_id_result.is_success:
            return group_id_result
        if not group_id_result.data or not group_id_result.data.get("GroupId"):
            return OperationResult.permanent_error(
                message=f"GroupId not found for group name {group_name}",
                error_code="GROUP_ID_NOT_FOUND",
            )
        group_id = group_id_result.data.get("GroupId")
        return self.describe_group(
            group_id=group_id,
            identity_store_id=identity_store_id,
            role_arn=role_arn,
            **kwargs,
        )

    def describe_user(
        self,
        user_id: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Describe a user from Identity Store.

        Args:
            user_id: User ID to retrieve
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with user details or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "describe_user",
            IdentityStoreId=store_id,
            UserId=user_id,
            **client_kwargs,
            **kwargs,
        )

    def describe_user_by_username(
        self,
        username: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Describe a user from Identity Store by username.
        Args:
            username: Username to retrieve (typically email)
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:
            OperationResult with user details or error
        """
        user_id_result = self.get_user_id_by_username(
            username,
            identity_store_id=identity_store_id,
            role_arn=role_arn,
            **kwargs,
        )
        if not user_id_result.is_success:
            return user_id_result

        if not user_id_result.data or not user_id_result.data.get("UserId"):
            return OperationResult.permanent_error(
                message=f"UserId not found for username {username}",
                error_code="USER_ID_NOT_FOUND",
            )

        user_id = user_id_result.data.get("UserId")
        return self.describe_user(
            user_id=user_id,
            identity_store_id=identity_store_id,
            role_arn=role_arn,
            **kwargs,
        )

    def get_batch_groups(
        self,
        group_ids: List[str],
        **kwargs,
    ) -> OperationResult:
        """Fetch multiple groups by their IDs using individual API calls.

        Args:
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
            response = self.describe_group(group_id, **kwargs)
            if response.is_success:
                results[group_id] = response.data
            else:
                results[group_id] = None
                log.warning(
                    "batch_group_fetch_failed",
                    group_id=group_id,
                    error=response.message,
                )

        log.info(
            "batch_groups_fetched", successful=sum(1 for v in results.values() if v)
        )
        return OperationResult.success(
            data=results, message=f"Fetched {len(results)} group(s)"
        )

    def get_batch_users(
        self,
        user_ids: List[str],
        **kwargs,
    ) -> OperationResult:
        """Fetch multiple users by their IDs using individual API calls.

        Args:
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
            response = self.describe_user(user_id, **kwargs)
            if response.is_success:
                results[user_id] = response.data
            else:
                results[user_id] = None
                log.warning(
                    "batch_user_fetch_failed",
                    user_id=user_id,
                    error=response.message,
                )

        log.info(
            "batch_users_fetched", successful=sum(1 for v in results.values() if v)
        )
        return OperationResult.success(
            data=results, message=f"Fetched {len(results)} user(s)"
        )

    def get_group_id_by_group_name(
        self,
        group_name: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get a group ID by its group name.

        Args:
            group_name: The name of the group to search for
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters for the API call
        Returns:
            OperationResult with group details or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            service_name="identitystore",
            method="get_group_id",
            IdentityStoreId=store_id,
            AlternateIdentifier={
                "UniqueAttribute": {
                    "AttributePath": "displayName",
                    "AttributeValue": group_name,
                }
            },
            **client_kwargs,
            **kwargs,
        )

    def get_group_membership_id(
        self,
        group_id: str,
        member_id: Dict[str, str],
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get a group membership ID by group ID and member ID.

        Args:
            group_id: ID of the group
            member_id: Dict with 'UserId' key for the member
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters for the API call
        Returns:
            OperationResult with membership ID or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "get_group_membership_id",
            IdentityStoreId=store_id,
            GroupId=group_id,
            MemberId=member_id,
            **client_kwargs,
            **kwargs,
        )

    def get_user_id_by_username(
        self,
        username: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """
        Get a user ID by username (email).

        Args:
            username (str): The username (typically email) to search for
            **kwargs: Additional parameters for the API call

        Returns:
            OperationResult: Standardized response model for external API integrations.
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            service_name="identitystore",
            method="get_user_id",
            IdentityStoreId=store_id,
            AlternateIdentifier={
                "UniqueAttribute": {
                    "AttributePath": "userName",
                    "AttributeValue": username,
                }
            },
            **client_kwargs,
            **kwargs,
        )

    def healthcheck(
        self, identity_store_id: Optional[str] = None, role_arn: Optional[str] = None
    ) -> OperationResult:
        """Lightweight health check for Identity Store.

        Calls `list_users` with a small page to validate connectivity and permissions.
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required for healthcheck",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_users",
            IdentityStoreId=store_id,
            max_retries=0,
            **client_kwargs,
        )

    def is_member_in_groups(
        self,
        user_id: str,
        group_ids: list[str],
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Check if a user is a member of a specific group.

        Args:
            user_id: ID of the user to check
            group_ids: List of IDs of the groups to check against
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with validation of the user's membership in the specified groups or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )
        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_group_memberships_for_member",
            IdentityStoreId=store_id,
            MemberId={"UserId": user_id},
            GroupIds=group_ids,
            **client_kwargs,
            **kwargs,
        )

    def list_group_memberships(
        self,
        group_id: str,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List group memberships in Identity Store.

        Args:
            group_id: ID of the group to list memberships for
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters (Filters, etc.)
        Returns:
            OperationResult with list of group memberships or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_group_memberships",
            IdentityStoreId=store_id,
            GroupId=group_id,
            **client_kwargs,
            **kwargs,
        )

    def list_group_memberships_for_member(
        self,
        member_id: Dict[str, str],
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List group memberships for a specific member in Identity Store.

        Args:
            member_id: Dict with 'UserId' key for the member
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters (Filters, etc.)
        Returns:
            OperationResult with list of group memberships or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_group_memberships_for_member",
            IdentityStoreId=store_id,
            MemberId=member_id,
            **client_kwargs,
            **kwargs,
        )

    def list_groups(
        self,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List groups in Identity Store.

        Args:
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters (Filters, etc.)
        Returns:
            OperationResult with list of groups or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_groups",
            IdentityStoreId=store_id,
            **client_kwargs,
            **kwargs,
        )

    def list_groups_with_memberships(
        self,
        identity_store_id: Optional[str] = None,
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
            aws: AWSClients instance
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
        groups_result = self.list_groups(
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
        group_ids: List[str] = []
        for g in groups:
            gid = g.get("GroupId")
            if isinstance(gid, str):
                group_ids.append(gid)

        memberships_by_group = self._fetch_group_memberships_parallel(
            group_ids, **(memberships_kwargs or {})
        )
        log.info("memberships_fetched", groups_with_members=len(memberships_by_group))

        # 4. Fetch all user details
        users_result = self.list_users(
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
        groups_with_memberships = self._assemble_groups_with_memberships(
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

    def list_users(
        self,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List users in Identity Store.

        Args:
            identity_store_id: Optional override for Identity Store ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters (Filters, etc.)

        Returns:
            OperationResult with list of users or error
        """
        store_id = identity_store_id or self._default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_users",
            IdentityStoreId=store_id,
            **client_kwargs,
            **kwargs,
        )

    def _fetch_group_memberships_parallel(
        self,
        group_ids: List[str],
        max_workers: int = 10,
        **kwargs,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch group memberships in parallel.

        Args:
            aws: AWSClients instance
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
                    self.list_group_memberships,
                    gid,
                    **(kwargs or {}),
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
                        memberships_by_group[gid] = []
                        log.warning("fetch_group_memberships_failed", group_id=gid)
                except Exception as exc:  # pylint: disable=broad-except
                    log.exception(
                        "fetch_group_memberships_exception", group_id=gid, exc=exc
                    )
                    memberships_by_group[gid] = []

        return memberships_by_group

    def _assemble_groups_with_memberships(
        self,
        groups: List[Dict],
        memberships_by_group: Mapping[str, Optional[List[Dict[str, Any]]]],
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
