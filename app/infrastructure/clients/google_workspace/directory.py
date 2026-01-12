"""Directory client for Google Workspace operations.

Provides type-safe access to Google Workspace Directory API (users, groups, members)
with consistent error handling and OperationResult return types.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, cast

import structlog

from infrastructure.clients.google_workspace.batch_executor import execute_batch_request
from infrastructure.clients.google_workspace.executor import execute_google_api_call
from infrastructure.clients.google_workspace.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


@dataclass
class ListGroupsWithMembersRequest:
    """Configuration for list_groups_with_members operation.

    Attributes:
        groups_kwargs: Additional kwargs for list_groups API call
        members_kwargs: Additional kwargs for get_batch_group_members API call
        users_kwargs: Additional kwargs for get_batch_users API call
        groups_filters: List of callables(group: dict) -> bool
                       Group is included if it matches ALL filters
        member_filters: List of callables(member: dict) -> bool
                       Group is included if it has AT LEAST ONE member matching ALL filters
        include_users_details: Whether to fetch and include user details for members
        exclude_empty_groups: Whether to exclude groups with no members
    """

    groups_filters: Optional[list[Callable]] = None
    member_filters: Optional[list[Callable]] = None
    groups_kwargs: Optional[dict] = field(default_factory=dict)
    members_kwargs: Optional[dict] = field(default_factory=dict)
    users_kwargs: Optional[dict] = field(default_factory=dict)
    include_users_details: bool = True
    exclude_empty_groups: bool = False


class DirectoryClient:
    """Client for Google Workspace Directory API operations.

    All methods return OperationResult for consistent error handling.
    Each method specifies resource-specific OAuth scopes as required by Google's Directory API.

    Args:
        session_provider: SessionProvider for authentication
        default_customer_id: Default customer ID (usually "my_customer")
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_customer_id: str = "my_customer",
    ) -> None:
        self._session_provider = session_provider
        self._default_customer_id = default_customer_id
        self._logger = logger.bind(component="directory_client")

    def get_user(
        self,
        user_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get a user by key (email or user ID).

        Args:
            user_key: User's primary email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with user data in data field
        """
        self._logger.debug("getting_user", user_key=user_key)

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.user.readonly"
                ],
                delegated_user_email=delegated_email,
            )
            request = service.users().get(userKey=user_key)
            return request.execute()

        return execute_google_api_call("get_user", api_call)

    def list_users(
        self,
        customer: Optional[str] = None,
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """List all users in domain with automatic pagination.

        Args:
            customer: Customer ID (defaults to "my_customer")
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters (maxResults, query, orderBy, etc.)

        Returns:
            OperationResult with list of users in data field
        """
        customer_id = customer or self._default_customer_id
        self._logger.debug("listing_users", customer=customer_id)

        def api_call() -> list[dict[str, Any]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.user.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            all_users: list[dict[str, Any]] = []
            request = service.users().list(customer=customer_id, **kwargs)

            while request is not None:
                response = request.execute()
                users = response.get("users", [])
                all_users.extend(users)

                request = service.users().list_next(request, response)

            return all_users

        return execute_google_api_call("list_users", api_call)

    def create_user(
        self,
        body: dict[str, Any],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new user in domain.

        Args:
            body: User resource body (must include primaryEmail, name, password)
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with created user data in data field
        """
        self._logger.info("creating_user", email=body.get("primaryEmail"))

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.user"],
                delegated_user_email=delegated_email,
            )
            request = service.users().insert(body=body)
            return request.execute()

        return execute_google_api_call("create_user", api_call)

    def update_user(
        self,
        user_key: str,
        body: dict[str, Any],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Update an existing user.

        Args:
            user_key: User's primary email or unique ID
            body: User resource body with fields to update
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with updated user data in data field
        """
        self._logger.info("updating_user", user_key=user_key)

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.user"],
                delegated_user_email=delegated_email,
            )
            request = service.users().update(userKey=user_key, body=body)
            return request.execute()

        return execute_google_api_call("update_user", api_call)

    def delete_user(
        self,
        user_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Delete a user from domain.

        Args:
            user_key: User's primary email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with success status (no data)
        """
        self._logger.info("deleting_user", user_key=user_key)

        def api_call() -> None:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.user"],
                delegated_user_email=delegated_email,
            )
            request = service.users().delete(userKey=user_key)
            request.execute()
            return None

        return execute_google_api_call("delete_user", api_call)

    def get_group(
        self,
        group_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get a group by key (email or group ID).

        Args:
            group_key: Group's email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with group data in data field
        """
        self._logger.debug("getting_group", group_key=group_key)

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.readonly"
                ],
                delegated_user_email=delegated_email,
            )
            request = service.groups().get(groupKey=group_key)
            return request.execute()

        return execute_google_api_call("get_group", api_call)

    def list_groups(
        self,
        customer: Optional[str] = None,
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """List all groups in domain with automatic pagination.

        Args:
            customer: Customer ID (defaults to "my_customer")
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters (maxResults, query, orderBy, etc.)

        Returns:
            OperationResult with list of groups in data field
        """
        customer_id = customer or self._default_customer_id
        self._logger.debug("listing_groups", customer=customer_id)

        def api_call() -> list[dict[str, Any]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            all_groups: list[dict[str, Any]] = []
            request = service.groups().list(customer=customer_id, **kwargs)

            while request is not None:
                response = request.execute()
                groups = response.get("groups", [])
                all_groups.extend(groups)

                request = service.groups().list_next(request, response)

            return all_groups

        return execute_google_api_call("list_groups", api_call)

    def create_group(
        self,
        body: dict[str, Any],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new group in domain.

        Args:
            body: Group resource body (must include email, name)
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with created group data in data field
        """
        self._logger.info("creating_group", email=body.get("email"))

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.group"],
                delegated_user_email=delegated_email,
            )
            request = service.groups().insert(body=body)
            return request.execute()

        return execute_google_api_call("create_group", api_call)

    def update_group(
        self,
        group_key: str,
        body: dict[str, Any],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Update an existing group.

        Args:
            group_key: Group's email or unique ID
            body: Group resource body with fields to update
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with updated group data in data field
        """
        self._logger.info("updating_group", group_key=group_key)

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.group"],
                delegated_user_email=delegated_email,
            )
            request = service.groups().update(groupKey=group_key, body=body)
            return request.execute()

        return execute_google_api_call("update_group", api_call)

    def delete_group(
        self,
        group_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Delete a group from domain.

        Args:
            group_key: Group's email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with success status (no data)
        """
        self._logger.info("deleting_group", group_key=group_key)

        def api_call() -> None:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.group"],
                delegated_user_email=delegated_email,
            )
            request = service.groups().delete(groupKey=group_key)
            request.execute()
            return None

        return execute_google_api_call("delete_group", api_call)

    def list_members(
        self,
        group_key: str,
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """List all members of a group with automatic pagination.

        Args:
            group_key: Group's email or unique ID
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters (maxResults, roles, etc.)

        Returns:
            OperationResult with list of members in data field
        """
        self._logger.debug("listing_members", group_key=group_key)

        def api_call() -> list[dict[str, Any]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            all_members: list[dict[str, Any]] = []
            request = service.members().list(groupKey=group_key, **kwargs)

            while request is not None:
                response = request.execute()
                members = response.get("members", [])
                all_members.extend(members)

                request = service.members().list_next(request, response)

            return all_members

        return execute_google_api_call("list_members", api_call)

    def add_member(
        self,
        group_key: str,
        body: dict[str, Any],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Add a member to a group.

        Args:
            group_key: Group's email or unique ID
            body: Member resource body (must include email, role)
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with member data in data field
        """
        self._logger.info(
            "adding_member", group_key=group_key, member_email=body.get("email")
        )

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.group.member"],
                delegated_user_email=delegated_email,
            )
            request = service.members().insert(groupKey=group_key, body=body)
            return request.execute()

        return execute_google_api_call("add_member", api_call)

    def remove_member(
        self,
        group_key: str,
        member_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Remove a member from a group.

        Args:
            group_key: Group's email or unique ID
            member_key: Member's email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with success status (no data)
        """
        self._logger.info("removing_member", group_key=group_key, member_key=member_key)

        def api_call() -> None:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=["https://www.googleapis.com/auth/admin.directory.group.member"],
                delegated_user_email=delegated_email,
            )
            request = service.members().delete(groupKey=group_key, memberKey=member_key)
            request.execute()
            return None

        return execute_google_api_call("remove_member", api_call)

    def get_member(
        self,
        group_key: str,
        member_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get a specific member from a group.

        Args:
            group_key: Group's email or unique ID
            member_key: Member's email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with member data in data field
        """
        self._logger.debug("getting_member", group_key=group_key, member_key=member_key)

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
                ],
                delegated_user_email=delegated_email,
            )
            request = service.members().get(groupKey=group_key, memberKey=member_key)
            return request.execute()

        return execute_google_api_call("get_member", api_call)

    def has_member(
        self,
        group_key: str,
        member_key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Check if a member exists in a group.

        Args:
            group_key: Group's email or unique ID
            member_key: Member's email or unique ID
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with boolean data indicating membership
        """
        self._logger.debug(
            "checking_member", group_key=group_key, member_key=member_key
        )

        def api_call() -> dict[str, Any]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
                ],
                delegated_user_email=delegated_email,
            )
            request = service.members().hasMember(
                groupKey=group_key, memberKey=member_key
            )
            return request.execute()

        return execute_google_api_call("has_member", api_call)

    def get_batch_users(
        self,
        user_keys: list[str],
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """Get multiple users using batch requests.

        Args:
            user_keys: List of user emails or IDs
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters for each user request

        Returns:
            OperationResult with dict mapping user_key to user data (or None if error)
        """
        self._logger.debug("getting_batch_users", user_keys=user_keys, kwargs=kwargs)

        def api_call() -> dict[str, Optional[dict]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.user.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            requests = []
            for user_key in user_keys:
                req = service.users().get(userKey=user_key, **kwargs)
                requests.append((user_key, req))

            resp = execute_batch_request(service, requests)
            if not resp.is_success:
                # Propagate batch error instead of returning empty dict
                raise RuntimeError(resp.message or "Batch request failed")

            results = (
                resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
            )
            users_by_key: dict[str, Optional[dict]] = {
                k: results.get(k) for k in user_keys
            }
            return users_by_key

        result = execute_google_api_call("get_batch_users", api_call)
        if result.is_success:
            return OperationResult.success(
                data=result.data, message="Batch users retrieved successfully"
            )
        return result

    def get_batch_groups(
        self,
        group_keys: list[str],
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """Get multiple groups using batch requests.

        Args:
            group_keys: List of group emails or IDs
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters for each group request

        Returns:
            OperationResult with dict mapping group_key to group data (or None if error)
        """
        self._logger.debug("getting_batch_groups", group_keys=group_keys, kwargs=kwargs)

        def api_call() -> dict[str, Optional[dict]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            requests = []
            for group_key in group_keys:
                req = service.groups().get(groupKey=group_key, **kwargs)
                requests.append((group_key, req))

            resp = execute_batch_request(service, requests)
            if not resp.is_success:
                # Propagate batch error instead of returning empty dict
                raise RuntimeError(resp.message or "Batch request failed")

            results = (
                resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
            )
            groups_by_key: dict[str, Optional[dict]] = {
                k: results.get(k) for k in group_keys
            }
            return groups_by_key

        result = execute_google_api_call("get_batch_groups", api_call)
        if result.is_success:
            return OperationResult.success(
                data=result.data, message="Batch groups retrieved successfully"
            )
        return result

    def get_batch_members_for_user(
        self,
        group_keys: list[str],
        user_key: str,
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """Get member objects for a user across multiple groups using batch requests.

        Args:
            group_keys: List of group emails or IDs
            user_key: User's email or unique ID
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters for each member request

        Returns:
            OperationResult with dict mapping group_key to member data (or None if not a member)
        """
        self._logger.debug(
            "getting_batch_members_for_user",
            group_keys=group_keys,
            user_key=user_key,
            kwargs=kwargs,
        )

        def api_call() -> dict[str, Optional[dict]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            requests = []
            for group_key in group_keys:
                req = service.members().get(
                    groupKey=group_key, memberKey=user_key, **kwargs
                )
                requests.append((group_key, req))

            resp = execute_batch_request(service, requests)
            if not resp.is_success:
                # Propagate batch error instead of returning empty dict
                raise RuntimeError(resp.message or "Batch request failed")

            results = (
                resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
            )
            members_by_group: dict[str, Optional[dict]] = {
                k: results.get(k) for k in group_keys
            }
            return members_by_group

        result = execute_google_api_call("get_batch_members_for_user", api_call)
        if result.is_success:
            return OperationResult.success(
                data=result.data,
                message="Batch members for user retrieved successfully",
            )
        return result

    def get_batch_group_members(
        self,
        group_keys: list[str],
        delegated_email: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult:
        """Get members for multiple groups using batch requests.

        Args:
            group_keys: List of group emails or IDs
            delegated_email: Email for domain-wide delegation
            **kwargs: Additional parameters for members.list API call

        Returns:
            OperationResult with dict mapping group_key to list of members
        """
        self._logger.debug(
            "getting_batch_group_members", group_keys=group_keys, kwargs=kwargs
        )

        def api_call() -> dict[str, list[dict]]:
            service = self._session_provider.get_service(
                "admin",
                "directory_v1",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.group.readonly"
                ],
                delegated_user_email=delegated_email,
            )

            requests = []
            for group_key in group_keys:
                req = service.members().list(groupKey=group_key, **kwargs)
                requests.append((group_key, req))

            resp = execute_batch_request(service, requests)
            if not resp.is_success:
                # Propagate batch error instead of returning empty dict
                raise RuntimeError(resp.message or "Batch request failed")

            results = (
                resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
            )
            members_by_group: dict[str, list[dict]] = {}

            for group_key in group_keys:
                group_result = results.get(group_key)
                if isinstance(group_result, dict):
                    members_by_group[group_key] = group_result.get("members", [])
                elif group_result is None:
                    members_by_group[group_key] = []
                else:
                    members_by_group[group_key] = []

            return members_by_group

        result = execute_google_api_call("get_batch_group_members", api_call)
        if result.is_success:
            return OperationResult.success(
                data=result.data, message="Batch group members retrieved successfully"
            )
        return result

    def list_groups_with_members(
        self,
        request: Optional[ListGroupsWithMembersRequest] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """List groups with members, optionally filtered at group and member levels.

        Args:
            request: ListGroupsWithMembersRequest configuration object.
                    If None, uses defaults (all groups, all members, with user details).
            delegated_email: Email for domain-wide delegation

        Returns:
            OperationResult with list of groups and their members

        Example:
            # List all groups with their members
            result = client.list_groups_with_members()

            # List groups starting with 'aws-' that contain 'production' in the email
            result = client.list_groups_with_members(
                ListGroupsWithMembersRequest(
                    groups_kwargs={"query": "email:aws-*"},  # API-level filter
                    groups_filters=[lambda g: "production" in g.get("email", "")],  # Post-process filter
                )
            )
        """
        if request is None:
            request = ListGroupsWithMembersRequest()

        self._logger.info("listing_groups_with_members", request=request)

        # Get groups
        groups_resp = self.list_groups(
            delegated_email=delegated_email, **(request.groups_kwargs or {})
        )
        self._logger.debug("fetched_groups", groups_count=len(groups_resp.data or []))
        if not groups_resp.is_success:
            return groups_resp

        # Apply group filters
        groups_list = groups_resp.data or []
        if request.groups_filters:
            groups_list = [
                g
                for g in groups_list
                if all(filter_fn(g) for filter_fn in request.groups_filters)
            ]

        if not groups_list:
            return OperationResult.success(
                data=[], message="No groups found matching filters"
            )

        # Get members for all groups
        group_keys = [g.get("email") for g in groups_list]
        members_resp = self.get_batch_group_members(
            group_keys,
            delegated_email=delegated_email,
            **(request.members_kwargs or {}),
        )
        if not members_resp.is_success:
            return members_resp

        members_by_group: dict[str, list[dict]] = (
            members_resp.data
            if isinstance(members_resp.data, dict)
            else {k: [] for k in group_keys}
        )

        # Assemble groups with members
        results = self._assemble_groups_with_members(
            groups_list, members_by_group, request.exclude_empty_groups
        )

        # Filter groups based on member criteria
        if request.member_filters:
            results = self._filter_groups_by_members(results, request.member_filters)

        # Fetch user details if requested
        if request.include_users_details and results:
            all_member_emails = set()
            for group in results:
                for member in group.get("members", []):
                    email = member.get("email")
                    if email:
                        all_member_emails.add(email)

            if all_member_emails:
                users_resp = self.get_batch_users(
                    list(all_member_emails),
                    delegated_email=delegated_email,
                    **(request.users_kwargs or {}),
                )
                if users_resp.is_success:
                    users_by_email = users_resp.data or {}
                    results = self._enrich_members_with_users(results, users_by_email)

        return OperationResult.success(
            data=results, message="Groups with members retrieved successfully"
        )

    def _assemble_groups_with_members(
        self,
        groups_list: list[dict[str, Any]],
        members_by_group: dict[str, list[dict[str, Any]]],
        exclude_empty_groups: bool = False,
    ) -> list[dict[str, Any]]:
        """Assemble groups with their members.

        Args:
            groups_list: List of group objects from API
            members_by_group: Dict mapping group key -> list of member objects
            exclude_empty_groups: Whether to exclude groups with no members

        Returns:
            List of groups with members assembled
        """
        results: list[dict[str, Any]] = []
        for g in groups_list:
            group_key = cast(str, g.get("email"))
            members = members_by_group.get(group_key, [])

            if exclude_empty_groups and not members:
                continue

            group_with_members = {**g, "members": members}
            results.append(group_with_members)

        return results

    def _enrich_members_with_users(
        self,
        groups_with_members: list[dict[str, Any]],
        users_by_email: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Enrich group members with user details.

        Args:
            groups_with_members: Groups with members already assembled
            users_by_email: Dict mapping email -> enriched user object

        Returns:
            Groups with enriched members
        """
        results: list[dict[str, Any]] = []
        for group in groups_with_members:
            enriched_members = []
            for member in group.get("members", []):
                email = cast(str, member.get("email"))
                user_details = users_by_email.get(email) if email else None

                if user_details:
                    enriched_member = {**member, "user": user_details}
                else:
                    enriched_member = member

                enriched_members.append(enriched_member)

            enriched_group = {**group, "members": enriched_members}
            results.append(enriched_group)

        return results

    def _filter_groups_by_members(
        self,
        groups_with_members: list[dict],
        member_filters: Optional[list] = None,
    ) -> list[dict]:
        """Filter groups based on member criteria.

        A group is included if it has AT LEAST ONE member matching ALL filter criteria.

        Args:
            groups_with_members: Groups with all members already assembled
            member_filters: List of callables(member: dict) -> bool
                           Group is included if ANY member matches ALL filters

        Returns:
            Filtered groups (with all their members intact)
        """
        if not member_filters:
            return groups_with_members

        filtered_groups = []
        for group in groups_with_members:
            members = group.get("members", [])
            has_matching_member = any(
                all(filter_fn(member) for filter_fn in member_filters)
                for member in members
            )

            if has_matching_member:
                filtered_groups.append(group)

        return filtered_groups
