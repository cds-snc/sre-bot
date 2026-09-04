"""Google Workspace implementation of DirectoryProvider."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from googleapiclient.errors import HttpError

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryGroupFailure,
    DirectoryGroupsWithMembers,
    DirectoryGroupWithMembers,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.directory.settings import DirectorySettings
from infrastructure.operations import OperationResult
from integrations.google_workspace.client import classify_google_error

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1 import (
        DirectoryResource as AdminDirectoryResource,  # pyright: ignore[reportMissingModuleSource]
    )

logger = structlog.get_logger()

T = TypeVar("T")

_NUM_RETRIES = 3
_USERS_PAGE_SIZE = 500
_GROUPS_PAGE_SIZE = 200
_MEMBERS_PAGE_SIZE = 200
# googleapiclient raises BatchError past MAX_BATCH_LIMIT (1000); stay well under it.
_BATCH_MAX_REQUESTS = 100


class GoogleDirectoryProvider:
    """DirectoryProvider backed by Google Workspace Admin SDK Directory API.

    Calls the discovery Resource directly via an injected, per-call scoped
    service factory (preserving today's least-privilege OAuth scoping) and
    classifies googleapiclient errors with classify_google_error.  Direct
    instantiation of Google API credentials or service clients inside this
    class is forbidden — use build_google_directory_provider() from the factory
    module instead.
    """

    def __init__(
        self,
        get_service: Callable[[list[str]], AdminDirectoryResource],
        directory_settings: DirectorySettings,
        customer_id: str = "my_customer",
    ) -> None:
        """Initialise with an injected, per-call scoped service factory.

        Args:
            get_service: Factory building a scoped Admin Directory Resource
                for a given OAuth scope list — called once per operation.
            directory_settings: Directory provider settings.
            customer_id: Google Workspace customer ID for directory operations.
        """
        self._get_service = get_service
        self._directory_settings = directory_settings
        self._customer_id = customer_id or "my_customer"
        self._logger = logger.bind(provider="google")

    def _map_sdk_exception(self, exc: Exception, operation: str) -> OperationResult[Any]:
        """Classify a raised googleapiclient exception into an OperationResult error."""
        status, error_code, retry_after = classify_google_error(exc)
        return OperationResult.error(
            status=status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="google",
            operation=operation,
        )

    def _call(self, operation: str, fn: Callable[[], Any]) -> OperationResult[Any]:
        """Execute a Directory API call, classifying googleapiclient errors."""
        try:
            return OperationResult.success(data=fn())
        except HttpError as exc:
            return self._map_sdk_exception(exc, operation)

    def _paginate(
        self,
        operation: str,
        resource: Any,
        request: Any,
        response_key: str,
        limit: int | None = None,
    ) -> OperationResult[list[dict[str, Any]]]:
        """Aggregate every page of an already-built Directory list request.

        Takes the built request rather than call parameters so each
        ``list(...)`` call stays type-checked against the stub at its call site.
        """

        def run() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            next_request = request
            while next_request is not None:
                response = next_request.execute(num_retries=_NUM_RETRIES)
                items.extend(response.get(response_key, []))
                if limit is not None and len(items) >= limit:
                    return items[:limit]
                next_request = resource.list_next(next_request, response)
            return items

        return self._call(operation, run)

    def _execute_batch_round(
        self,
        service: AdminDirectoryResource,
        requests: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, HttpError]]:
        """Run one batch round, returning per-key responses and per-key errors.

        Chunked because BatchHttpRequest.add raises BatchError past MAX_BATCH_LIMIT.
        Callers pick their own failure policy — nothing is classified here.
        """
        responses: dict[str, Any] = {}
        errors: dict[str, HttpError] = {}

        # response is Any because the stub types this parameter HttpRequest, not the payload.
        def callback(request_id: str, response: Any, exception: HttpError | None) -> None:
            if exception is not None:
                errors[request_id] = exception
            else:
                responses[request_id] = response

        keys = list(requests)
        for start in range(0, len(keys), _BATCH_MAX_REQUESTS):
            batch = service.new_batch_http_request(callback=callback)
            for key in keys[start : start + _BATCH_MAX_REQUESTS]:
                batch.add(requests[key], request_id=key)
            batch.execute()

        return responses, errors

    def _batch_list_members(
        self,
        service: AdminDirectoryResource,
        group_keys: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, HttpError]]:
        """Fetch every member page for each group, re-batching only unfinished groups."""
        members_resource = service.members()
        raw_members: dict[str, list[dict[str, Any]]] = {key: [] for key in group_keys}
        errors: dict[str, HttpError] = {}
        pending: dict[str, Any] = {key: members_resource.list(groupKey=key, maxResults=_MEMBERS_PAGE_SIZE) for key in group_keys}

        while pending:
            responses, round_errors = self._execute_batch_round(service, pending)
            errors.update(round_errors)
            next_pending: dict[str, Any] = {}
            for key, response in responses.items():
                raw_members[key].extend(response.get("members", []) or [])
                next_request = members_resource.list_next(pending[key], response)
                if next_request is not None:
                    next_pending[key] = next_request
            pending = next_pending

        return raw_members, errors

    def _normalize_member_types(self, include_member_types: set[str] | None) -> OperationResult[set[str] | None]:
        """Normalise and validate the requested member-type filter."""
        if include_member_types is None:
            return OperationResult.success(data=None)

        allowed = {str(member_type).strip().upper() for member_type in include_member_types if str(member_type).strip()}
        if not allowed:
            return OperationResult.permanent_error(
                message="include_member_types must contain at least one type",
                error_code="DIRECTORY_MEMBER_TYPES_INVALID",
            )

        return OperationResult.success(data=allowed)

    def _map_members(self, items: list[dict[str, Any]], allowed: set[str] | None) -> list[DirectoryMember]:
        """Map raw member payloads into canonical members, applying the type filter."""
        members: list[DirectoryMember] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            member_type = str(item.get("type") or "").strip().upper()
            if allowed is not None and member_type and member_type not in allowed:
                continue

            member = self._build_directory_member(item)
            if member is not None:
                members.append(member)

        return members

    def _build_group_failure(self, group_email: str, exc: HttpError) -> DirectoryGroupFailure:
        """Classify a per-group batch error into a typed failure entry."""
        status, error_code, _retry_after = classify_google_error(exc)
        return DirectoryGroupFailure(
            group_email=group_email,
            status=status,
            error_code=error_code,
            message=str(exc),
        )

    def _normalize_email(self, value: str) -> str:
        """Normalize email-form identifiers used by the shared contract.

        Values are stripped and lowercased only — callers supply fully-qualified
        keys.
        """
        return value.strip().lower()

    def _extract_email(self, item: dict[str, Any], *keys: str) -> str:
        """Extract and normalize the first available email-like value."""

        for key in keys:
            value = str(item.get(key) or "").strip()
            if value:
                return self._normalize_email(value)

        emails = item.get("emails")
        if isinstance(emails, list):
            first_email = ""
            for email_item in emails:
                if not isinstance(email_item, dict):
                    continue

                address = str(email_item.get("address") or email_item.get("value") or "").strip()
                if not address:
                    continue

                normalized_address = self._normalize_email(address)
                if not first_email:
                    first_email = normalized_address
                if email_item.get("primary") is True:
                    return normalized_address

            if first_email:
                return first_email

        return ""

    def _extract_group_aliases(self, item: dict[str, Any]) -> list[str]:
        """Return normalized group aliases from Google group payload variants."""

        aliases: list[str] = []
        for key in ["aliases", "nonEditableAliases"]:
            raw_aliases = item.get(key)
            if not isinstance(raw_aliases, list):
                continue
            for raw_alias in raw_aliases:
                if not isinstance(raw_alias, str):
                    continue
                normalized_alias = self._normalize_email(raw_alias)
                if normalized_alias and normalized_alias not in aliases:
                    aliases.append(normalized_alias)
        return aliases

    def _extract_display_name(self, item: dict[str, Any]) -> str | None:
        """Extract a stable display name from provider payload variants."""

        name = item.get("name")
        if isinstance(name, dict):
            full_name = str(name.get("fullName") or "").strip()
            if full_name:
                return full_name

            display_name = str(name.get("displayName") or "").strip()
            if display_name:
                return display_name

            given_name = str(name.get("givenName") or "").strip()
            family_name = str(name.get("familyName") or "").strip()
            combined_name = " ".join(part for part in [given_name, family_name] if part).strip()
            if combined_name:
                return combined_name

        if isinstance(name, str):
            normalized_name = name.strip()
            if normalized_name:
                return normalized_name

        for key in ["displayName", "fullName"]:
            value = str(item.get(key) or "").strip()
            if value:
                return value

        return None

    def _extract_name_parts(self, item: dict[str, Any]) -> tuple[str | None, str | None]:
        """Extract (given_name, family_name) from provider payload variants."""

        name = item.get("name")
        if isinstance(name, dict):
            given_name = str(name.get("givenName") or "").strip() or None
            family_name = str(name.get("familyName") or "").strip() or None
            return given_name, family_name

        return None, None

    def _typed_error(self, result: OperationResult[Any]) -> OperationResult[T]:
        """Rebox an error result without leaking provider-native payload data."""

        return OperationResult.error(
            status=result.status,
            message=result.message,
            error_code=result.error_code,
            retry_after=result.retry_after,
            provider=result.provider,
            operation=result.operation,
        )

    def _build_directory_user(self, item: dict[str, Any]) -> OperationResult[DirectoryUser]:
        """Convert a Google user record into a canonical directory user."""

        email = self._extract_email(item, "primaryEmail", "email")
        provider_user_id = str(item.get("id") or item.get("userId") or "").strip()
        if not email:
            return OperationResult.permanent_error(
                message="Directory user is missing primary email",
                error_code="DIRECTORY_USER_EMAIL_REQUIRED",
            )
        if not provider_user_id:
            return OperationResult.permanent_error(
                message="Directory user is missing provider user ID",
                error_code="DIRECTORY_USER_ID_REQUIRED",
            )

        display_name = self._extract_display_name(item)
        given_name, family_name = self._extract_name_parts(item)

        is_active = None
        if "suspended" in item:
            is_active = not bool(item.get("suspended"))

        return OperationResult.success(
            data=DirectoryUser(
                email=email,
                provider_user_id=provider_user_id,
                display_name=display_name,
                given_name=given_name,
                family_name=family_name,
                is_active=is_active,
                provider="google",
            )
        )

    def _build_directory_member(self, item: dict[str, Any]) -> DirectoryMember | None:
        """Convert a Google member record into a canonical directory member."""

        member_email = self._extract_email(item, "email", "primaryEmail")
        if not member_email:
            return None

        return DirectoryMember(
            email=member_email,
            membership_id=str(item.get("id") or "").strip() or None,
            provider_user_id=None,
            member_type=(str(item.get("type") or "").strip().upper() or None),
            role=item.get("role"),
            provider="google",
        )

    def _build_group(self, item: dict[str, Any]) -> OperationResult[DirectoryGroup]:
        """Convert a Google group record into a canonical directory group."""
        group_email = self._extract_email(item, "email", "groupEmail")
        if not group_email:
            return OperationResult.permanent_error(
                message="Directory group is missing email",
                error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
            )

        provider_group_id = str(item.get("id") or item.get("groupId") or "").strip()
        if not provider_group_id:
            return OperationResult.permanent_error(
                message="Directory group is missing provider group ID",
                error_code="DIRECTORY_GROUP_ID_REQUIRED",
            )

        local_part, _, _ = group_email.partition("@")

        return OperationResult.success(
            data=DirectoryGroup(
                group_email=group_email,
                group_slug=local_part,
                provider_group_id=provider_group_id,
                name=item.get("name") or item.get("displayName"),
                description=item.get("description"),
                provider="google",
                aliases=tuple(self._extract_group_aliases(item)),
            )
        )

    def warmup(self) -> OperationResult[None]:
        """Validate connectivity by fetching the configured customer.

        Returns:
            OperationResult: success when the API responds successfully.
        """
        log = logger.bind(provider="google", operation="warmup")
        log.info("directory_warmup_started")
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.customer.readonly"])
        result = self._call(
            "warmup",
            lambda: service.customers().get(customerKey=self._customer_id).execute(num_retries=_NUM_RETRIES),
        )
        if result.is_success:
            log.info("directory_warmup_completed")
            return OperationResult.success()

        log.error("directory_warmup_failed", error=result.message)
        return self._typed_error(result)

    def health_check(self) -> OperationResult[None]:
        """Return a fast liveness result without making remote calls.

        Returns:
            OperationResult: always success.
        """
        return OperationResult.success()

    def get_user(self, email: str) -> OperationResult[DirectoryUser]:
        """Return a canonical directory user by email."""
        self._logger.info("getting_user", email=email)
        normalized_email = self._normalize_email(email)
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.user.readonly"])
        result = self._call(
            "get_user",
            lambda: service.users().get(userKey=normalized_email).execute(num_retries=_NUM_RETRIES),
        )
        self._logger.info(
            "get_user_result",
            success=result.is_success,
            error=result.message,
            data=result.data,
        )
        if not result.is_success:
            return self._typed_error(result)

        user_payload = result.data if isinstance(result.data, dict) else {}
        user_result = self._build_directory_user(user_payload)
        if not user_result.is_success:
            return self._typed_error(user_result)

        if user_result.data is None:
            return OperationResult.permanent_error(
                message="Directory user mapping returned no canonical user",
                error_code="DIRECTORY_USER_MAPPING_INVALID",
            )

        return OperationResult.success(data=user_result.data)

    def list_users(self, query: str = "", limit: int | None = None) -> OperationResult[list[DirectoryUser]]:
        """Return canonical users matching a query."""

        if limit is not None and limit <= 0:
            return OperationResult.success(data=[])

        max_results = min(limit, _USERS_PAGE_SIZE) if limit is not None else _USERS_PAGE_SIZE

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.user.readonly"])
        users_resource = service.users()
        result = self._paginate(
            "list_users",
            users_resource,
            users_resource.list(customer=self._customer_id, maxResults=max_results, query=query or None),
            "users",
            limit=limit,
        )
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory users payload is not a list",
                error_code="DIRECTORY_USERS_PAYLOAD_INVALID",
            )

        users: list[DirectoryUser] = []
        for item in result.data:
            if not isinstance(item, dict):
                return OperationResult.permanent_error(
                    message="Directory users payload contains an invalid entry",
                    error_code="DIRECTORY_USERS_PAYLOAD_INVALID",
                )

            user_result = self._build_directory_user(item)
            if not user_result.is_success:
                return self._typed_error(user_result)

            if user_result.data is None:
                return OperationResult.permanent_error(
                    message="Directory user mapping returned no canonical user",
                    error_code="DIRECTORY_USER_MAPPING_INVALID",
                )
            users.append(user_result.data)

        return OperationResult.success(data=users)

    def get_group_members(
        self,
        group_key: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[list[DirectoryMember]]:
        """Return the member list for a group.

        Args:
            group_key: Fully-qualified group email — normalised to lowercase.
            include_member_types: Optional set of member types to include
                (for example {"USER"}, {"GROUP"}, or both). Defaults to no
                filtering.

        Returns:
            OperationResult: success with the DirectoryMember list for the group.
        """
        normalized_group_key = self._normalize_email(group_key)
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member.readonly"])
        members_resource = service.members()
        result = self._paginate(
            "get_group_members",
            members_resource,
            members_resource.list(groupKey=normalized_group_key, includeDerivedMembership=True),
            "members",
        )
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory members payload is not a list",
                error_code="DIRECTORY_MEMBERS_PAYLOAD_INVALID",
            )

        allowed_member_types = None
        if include_member_types is not None:
            allowed_member_types = {
                str(member_type).strip().upper() for member_type in include_member_types if str(member_type).strip()
            }

        if include_member_types is not None and not allowed_member_types:
            return OperationResult.permanent_error(
                message="include_member_types must contain at least one type",
                error_code="DIRECTORY_MEMBER_TYPES_INVALID",
            )

        members: list[DirectoryMember] = []
        for item in result.data:
            if not isinstance(item, dict):
                continue

            member_type = str(item.get("type") or "").strip().upper()
            if allowed_member_types is not None and member_type and member_type not in allowed_member_types:
                continue

            member = self._build_directory_member(item)
            if member is not None:
                members.append(member)

        return OperationResult.success(data=members)

    def get_group_members_batch(
        self,
        group_keys: list[str],
        include_member_types: set[str] | None = None,
    ) -> OperationResult[dict[str, list[DirectoryMember]]]:
        """Return the member list for multiple groups in a single batch call.

        Uses the Google Admin batch API so cost is one batched round-trip per
        chunk of groups per member-page depth, rather than one call per group.
        Fails as a whole when any group's batch item fails.

        Args:
            group_keys: Fully-qualified group emails — normalised to lowercase.
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). Defaults to no filtering.

        Returns:
            OperationResult: success with a dict mapping group_key to
            DirectoryMember list.
        """
        if not group_keys:
            return OperationResult.success(data={})

        member_types_result = self._normalize_member_types(include_member_types)
        if not member_types_result.is_success:
            return self._typed_error(member_types_result)

        normalized_keys = [self._normalize_email(key) for key in group_keys]
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.readonly"])
        raw_members, errors = self._batch_list_members(service, normalized_keys)

        if errors:
            first_error = next(iter(errors.values()))
            return self._typed_error(self._map_sdk_exception(first_error, "get_group_members_batch"))

        allowed = member_types_result.data
        return OperationResult.success(data={key: self._map_members(items, allowed) for key, items in raw_members.items()})

    def get_group(self, group_key: str) -> OperationResult[DirectoryGroup]:
        """Return a canonical group by key.

        Args:
            group_key: Fully-qualified group email — normalised to lowercase.

        Returns:
            OperationResult: success with the canonical DirectoryGroup.
        """
        normalized_group_key = self._normalize_email(group_key)
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.readonly"])
        result = self._call(
            "get_group",
            lambda: service.groups().get(groupKey=normalized_group_key).execute(num_retries=_NUM_RETRIES),
        )
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, dict):
            return OperationResult.permanent_error(
                message="Directory group payload is not a dict",
                error_code="DIRECTORY_GROUP_PAYLOAD_INVALID",
            )

        group_result = self._build_group(result.data)
        if not group_result.is_success:
            return self._typed_error(group_result)

        return OperationResult.success(data=group_result.data)

    def add_group_member(
        self,
        group_key: str,
        user_email: str,
        role: str = "MEMBER",
    ) -> OperationResult[DirectoryMember]:
        """Add a membership to a group.

        Args:
            group_key: Fully-qualified group email — normalised to lowercase.
            user_email: User email to add — normalised to lowercase.
            role: Membership role hint (default: MEMBER, valid values: MEMBER, MANAGER, OWNER).

        Returns:
            OperationResult: success with the added DirectoryMember.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)
        normalized_role = role.strip().upper() if role.strip() else "MEMBER"

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member"])
        result = self._call(
            "add_member",
            lambda: (
                service.members()
                .insert(
                    groupKey=normalized_group,
                    body={"email": normalized_user_email, "role": normalized_role},
                )
                .execute(num_retries=_NUM_RETRIES)
            ),
        )
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, dict):
            return OperationResult.permanent_error(
                message="Directory member payload is not a dict",
                error_code="DIRECTORY_MEMBER_PAYLOAD_INVALID",
            )

        member_payload = dict(result.data)
        if not str(member_payload.get("role") or "").strip():
            member_payload["role"] = normalized_role

        member = self._build_directory_member(member_payload)
        if member is None:
            return OperationResult.permanent_error(
                message="Directory member is missing email",
                error_code="DIRECTORY_MEMBER_EMAIL_REQUIRED",
            )

        return OperationResult.success(data=member)

    def remove_group_member(
        self,
        group_key: str,
        user_email: str,
    ) -> OperationResult[None]:
        """Remove a membership from a group.

        Args:
            group_key: Fully-qualified group email — normalised to lowercase.
            user_email: User email to remove — normalised to lowercase.

        Returns:
            OperationResult: success with no payload.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member"])
        result = self._call(
            "remove_member",
            lambda: (
                service.members()
                .delete(groupKey=normalized_group, memberKey=normalized_user_email)
                .execute(num_retries=_NUM_RETRIES)
            ),
        )
        if not result.is_success:
            return self._typed_error(result)

        return OperationResult.success()

    def check_membership(self, group_key: str, user_email: str) -> OperationResult[MembershipCheckResult]:
        """Check whether a user is a member of a group.

        Uses the members.hasMember API for a single-call, server-side check
        that includes transitive membership (users nested inside sub-groups
        are correctly resolved as members).

        Args:
            group_key: Fully-qualified group email — normalised to lowercase.
            user_email: User email to check.

        Returns:
            OperationResult: success with the MembershipCheckResult.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member.readonly"])
        result = self._call(
            "has_member",
            lambda: (
                service.members()
                .hasMember(groupKey=normalized_group, memberKey=normalized_user_email)
                .execute(num_retries=_NUM_RETRIES)
            ),
        )
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, dict):
            return OperationResult.permanent_error(
                message="Directory hasMember payload is not a dict",
                error_code="DIRECTORY_MEMBERSHIP_PAYLOAD_INVALID",
            )

        is_member = bool(result.data.get("isMember", False))
        membership = MembershipCheckResult(
            group_email=normalized_group,
            group_slug=normalized_group.split("@", 1)[0],
            provider_group_id=None,
            user_email=normalized_user_email,
            is_member=is_member,
        )
        return OperationResult.success(data=membership)

    def list_groups(self, query: str = "", limit: int | None = None) -> OperationResult[list[DirectoryGroup]]:
        """List groups matching a Google Admin Directory query.

        Args:
            query: Google Admin Directory search clause(s). Empty string lists all
                groups without query filtering. Bare strings without a field operator
                are translated to ``email:{query}*``. Queries containing ``:`` or ``=``
                are passed through unchanged.
            limit: Maximum number of groups to return, or None for all groups.

        Returns:
            OperationResult: success with the matching DirectoryGroup list.
        """
        if limit is not None and limit <= 0:
            return OperationResult.success(data=[])

        max_results = min(limit, _GROUPS_PAGE_SIZE) if limit is not None else _GROUPS_PAGE_SIZE

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.readonly"])
        groups_resource = service.groups()

        query_str = query.strip()
        if not query_str:
            request = groups_resource.list(customer=self._customer_id, maxResults=max_results)
        else:
            google_query = f"email:{query_str}*" if ":" not in query_str and "=" not in query_str else query_str
            request = groups_resource.list(customer=self._customer_id, maxResults=max_results, query=google_query)

        result = self._paginate(
            "list_groups",
            groups_resource,
            request,
            "groups",
            limit=limit,
        )

        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory groups payload is not a list",
                error_code="DIRECTORY_GROUPS_PAYLOAD_INVALID",
            )

        groups: list[DirectoryGroup] = []
        skipped_count = 0
        for item in result.data:
            if not isinstance(item, dict):
                return OperationResult.permanent_error(
                    message="Directory groups payload contains an invalid entry",
                    error_code="DIRECTORY_GROUPS_PAYLOAD_INVALID",
                )

            group_result = self._build_group(item)
            if not group_result.is_success or group_result.data is None:
                provider_group_id = str(item.get("id") or item.get("groupId") or "").strip() or "<unknown>"
                self._logger.warning(
                    "directory_group_skipped",
                    provider_group_id=provider_group_id,
                    error_code=group_result.error_code,
                )
                skipped_count += 1
                continue

            groups.append(group_result.data)

        self._logger.info(
            "directory_groups_listed",
            returned=len(groups),
            skipped=skipped_count,
        )

        return OperationResult.success(data=groups[:limit] if limit is not None else groups)

    def list_groups_with_members(
        self,
        query: str = "",
        limit: int | None = None,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[DirectoryGroupsWithMembers]:
        """List groups together with their members in one batched composition.

        Groups whose members could not be fetched are returned in ``failures``
        rather than failing the whole result; groups with zero members are
        included.

        Args:
            query: Google Admin Directory search clause(s), as for ``list_groups``.
            limit: Maximum number of groups to return, or None for all groups.
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). Defaults to no filtering.

        Returns:
            OperationResult: success with the DirectoryGroupsWithMembers payload.
        """
        groups_result = self.list_groups(query=query, limit=limit)
        if not groups_result.is_success:
            return self._typed_error(groups_result)

        if not groups_result.data:
            return OperationResult.success(data=DirectoryGroupsWithMembers())

        member_types_result = self._normalize_member_types(include_member_types)
        if not member_types_result.is_success:
            return self._typed_error(member_types_result)

        allowed = member_types_result.data
        group_by_email = {group.group_email: group for group in groups_result.data}

        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member.readonly"])
        raw_members, errors = self._batch_list_members(service, list(group_by_email))

        groups_with_members: list[DirectoryGroupWithMembers] = []
        failures: list[DirectoryGroupFailure] = []
        for group_email, group in group_by_email.items():
            error = errors.get(group_email)
            if error is not None:
                failures.append(self._build_group_failure(group_email, error))
                continue

            groups_with_members.append(
                DirectoryGroupWithMembers(
                    group=group,
                    members=tuple(self._map_members(raw_members.get(group_email, []), allowed)),
                )
            )

        self._logger.info(
            "directory_groups_with_members_listed",
            returned=len(groups_with_members),
            failed=len(failures),
        )

        return OperationResult.success(
            data=DirectoryGroupsWithMembers(
                groups=tuple(groups_with_members),
                failures=tuple(failures),
            )
        )

    def get_user_groups(self, user_email: str) -> OperationResult[list[DirectoryGroup]]:
        """Return all groups the user is a direct member of.

        Uses ``groups.list(userKey=...)`` — the inverse group lookup — to fetch
        every group the user belongs to in a single paginated call instead of
        calling ``hasMember`` once per candidate group.  No domain or naming
        filtering is applied; callers decide which groups are in scope.

        Args:
            user_email: Canonical user email, normalised to lowercase.

        Returns:
            OperationResult: success with the list of DirectoryGroup the user
            belongs to.
        """
        log = self._logger.bind(operation="get_user_groups", user_email=user_email)
        normalized_email = self._normalize_email(user_email)
        service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.readonly"])
        groups_resource = service.groups()
        result = self._paginate(
            "list_user_groups",
            groups_resource,
            groups_resource.list(userKey=normalized_email),
            "groups",
        )
        log.debug(
            "list_user_groups_result",
            success=result.is_success,
            error=result.message,
            data=result.data,
        )
        if not result.is_success:
            log.error("list_user_groups_failed", error=result.message)
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory user groups payload is not a list",
                error_code="DIRECTORY_USER_GROUPS_PAYLOAD_INVALID",
            )

        groups: list[DirectoryGroup] = []
        for item in result.data:
            if not isinstance(item, dict):
                return OperationResult.permanent_error(
                    message="Directory user groups payload contains an invalid entry",
                    error_code="DIRECTORY_USER_GROUPS_PAYLOAD_INVALID",
                )

            group_result = self._build_group(item)
            if not group_result.is_success or group_result.data is None:
                provider_group_id = str(item.get("id") or item.get("groupId") or "").strip() or "<unknown>"
                log.warning(
                    "directory_group_skipped",
                    provider_group_id=provider_group_id,
                    error_code=group_result.error_code,
                )
                continue

            groups.append(group_result.data)

        return OperationResult.success(data=groups)
