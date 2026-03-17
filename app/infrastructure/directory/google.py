"""Google Workspace implementation of DirectoryProvider."""

from typing import Any, TypeVar

import structlog

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.configuration.infrastructure import DirectorySettings
from infrastructure.directory import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.directory.provider import (
    DirectoryGroupsData,
    DirectoryMembershipData,
    DirectoryMembersData,
    DirectoryUserData,
    DirectoryUsersData,
)
from infrastructure.operations import OperationResult

logger = structlog.get_logger()

T = TypeVar("T")


class GoogleDirectoryProvider:
    """DirectoryProvider backed by Google Workspace Directory API.

    Receives a GoogleWorkspaceClients facade injected by the factory.  Direct
    instantiation of Google API credentials or service clients inside this
    class is forbidden — use build_google_directory_provider() from the factory
    module instead.
    """

    def __init__(
        self,
        google_clients: GoogleWorkspaceClients,
        directory_settings: DirectorySettings,
    ) -> None:
        """Initialise with injected Google Workspace clients facade.

        Args:
            google_clients: Configured GoogleWorkspaceClients facade.
            directory_settings: Directory provider settings.
        """
        self._directory = google_clients.directory
        self._directory_settings = directory_settings
        self._managed_group_domain = (
            directory_settings.managed_group_domain.strip().lower()
        )
        self._logger = logger.bind(provider="google")

    def _normalize_email(self, value: str) -> str:
        """Normalize email-form identifiers used by the shared contract."""

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

                address = str(
                    email_item.get("address") or email_item.get("value") or ""
                ).strip()
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
            combined_name = " ".join(
                part for part in [given_name, family_name] if part
            ).strip()
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

    def _build_directory_user(
        self, item: dict[str, Any]
    ) -> OperationResult[DirectoryUser]:
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

        is_active = None
        if "suspended" in item:
            is_active = not bool(item.get("suspended"))

        return OperationResult.success(
            data=DirectoryUser(
                email=email,
                provider_user_id=provider_user_id,
                display_name=display_name,
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
            role=item.get("role"),
            provider="google",
        )

    def _build_directory_group(
        self, item: dict[str, Any]
    ) -> OperationResult[DirectoryGroup | None]:
        """Convert a Google group record into a canonical directory group."""

        group_email = self._extract_email(item, "email", "groupEmail")
        if not group_email:
            if self._directory_settings.enforce_managed_group_email:
                return OperationResult.permanent_error(
                    message="Managed directory group is missing provider-returned email",
                    error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
                )
            return OperationResult.success(data=None)

        local_part, _, domain = group_email.partition("@")
        if self._managed_group_domain and domain != self._managed_group_domain:
            return OperationResult.permanent_error(
                message="Managed directory group email does not match configured domain",
                error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH",
            )

        provider_group_id = str(item.get("id") or item.get("groupId") or "").strip()
        if not provider_group_id:
            return OperationResult.permanent_error(
                message="Managed directory group is missing provider group ID",
                error_code="DIRECTORY_GROUP_ID_REQUIRED",
            )

        return OperationResult.success(
            data=DirectoryGroup(
                group_email=group_email,
                group_slug=local_part,
                provider_group_id=provider_group_id,
                name=item.get("name") or item.get("displayName"),
                description=item.get("description"),
                provider="google",
            )
        )

    def warmup(self) -> OperationResult[None]:
        """Validate connectivity by fetching the configured customer.

        Returns:
            OperationResult: success when the API responds successfully.
        """
        log = logger.bind(provider="google", operation="warmup")
        log.info("directory_warmup_started")
        result = self._directory.health_check()
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

    def get_user(self, email: str) -> OperationResult[DirectoryUserData]:
        """Return a canonical directory user by email."""
        self._logger.info("getting_user", email=email)
        result = self._directory.get_user(self._normalize_email(email))
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

        return OperationResult.success(data={"user": user_result.data})

    def list_users(
        self, query: str = "", limit: int = 100
    ) -> OperationResult[DirectoryUsersData]:
        """Return canonical users matching a query."""

        if limit <= 0:
            return OperationResult.success(data={"users": []})

        list_kwargs: dict[str, Any] = {"maxResults": limit}
        if query:
            list_kwargs["query"] = query

        result = self._directory.list_users(**list_kwargs)
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory users payload is not a list",
                error_code="DIRECTORY_USERS_PAYLOAD_INVALID",
            )

        users: list[DirectoryUser] = []
        for item in result.data[:limit]:
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

        return OperationResult.success(data={"users": users})

    def get_group_members(
        self, group_key: str
    ) -> OperationResult[DirectoryMembersData]:
        """Return the member list for a group.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.

        Returns:
            OperationResult: success with data={"members": list[DirectoryMember]}.
        """
        result = self._directory.list_members(self._normalize_email(group_key))
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory members payload is not a list",
                error_code="DIRECTORY_MEMBERS_PAYLOAD_INVALID",
            )

        members: list[DirectoryMember] = []
        for item in result.data:
            if not isinstance(item, dict):
                continue
            member = self._build_directory_member(item)
            if member is not None:
                members.append(member)

        return OperationResult.success(data={"members": members})

    def check_membership(
        self, group_key: str, user_email: str
    ) -> OperationResult[DirectoryMembershipData]:
        """Check whether a user is a member of a group.

        Uses the members.hasMember API for a single-call, server-side check
        that includes transitive membership (users nested inside sub-groups
        are correctly resolved as members).

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.
            user_email: User email to check.

        Returns:
            OperationResult: success with data={"membership": MembershipCheckResult}.
                Returns the error result unchanged when hasMember fails.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)

        result = self._directory.has_member(normalized_group, normalized_user_email)
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
        return OperationResult.success(data={"membership": membership})

    def list_groups(self, query: str) -> OperationResult[DirectoryGroupsData]:
        """List groups matching a query string.

        Args:
            query: IDP-specific query string passed to the Directory API.

        Returns:
            OperationResult: success with data={"groups": list[DirectoryGroup]}.
        """
        result = self._directory.list_groups(query=query)
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory groups payload is not a list",
                error_code="DIRECTORY_GROUPS_PAYLOAD_INVALID",
            )

        groups: list[DirectoryGroup] = []
        for item in result.data:
            if not isinstance(item, dict):
                return OperationResult.permanent_error(
                    message="Directory groups payload contains an invalid entry",
                    error_code="DIRECTORY_GROUPS_PAYLOAD_INVALID",
                )

            group_result = self._build_directory_group(item)
            if not group_result.is_success:
                return self._typed_error(group_result)

            if group_result.data is not None:
                groups.append(group_result.data)

        return OperationResult.success(data={"groups": groups})
