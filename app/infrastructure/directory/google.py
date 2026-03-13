"""Google Workspace implementation of DirectoryProvider."""

from typing import Any

import structlog

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.configuration.infrastructure import DirectorySettings
from infrastructure.directory import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult

logger = structlog.get_logger()


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

    def _build_directory_user(self, item: dict[str, Any]) -> OperationResult:
        """Convert a Google user record into a canonical directory user."""

        email = self._normalize_email(str(item.get("primaryEmail") or ""))
        provider_user_id = str(item.get("id") or "").strip()
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

        display_name = item.get("name")
        if isinstance(display_name, dict):
            display_name = display_name.get("fullName")

        is_active = None
        if "suspended" in item:
            is_active = not bool(item.get("suspended"))

        return OperationResult.success(
            data={
                "user": DirectoryUser(
                    email=email,
                    provider_user_id=provider_user_id,
                    display_name=str(display_name) if display_name else None,
                    is_active=is_active,
                    provider="google",
                )
            }
        )

    def _build_directory_member(self, item: dict[str, Any]) -> DirectoryMember:
        """Convert a Google member record into a canonical directory member."""

        return DirectoryMember(
            email=self._normalize_email(str(item.get("email") or "")),
            membership_id=item.get("id"),
            provider_user_id=None,
            role=item.get("role"),
            provider="google",
        )

    def _build_directory_group(self, item: dict[str, Any]) -> OperationResult:
        """Convert a Google group record into a canonical directory group."""

        group_email = self._normalize_email(str(item.get("email") or ""))
        if not group_email:
            if self._directory_settings.enforce_managed_group_email:
                return OperationResult.permanent_error(
                    message="Managed directory group is missing provider-returned email",
                    error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
                )
            return OperationResult.success(data={"group": None})

        local_part, _, domain = group_email.partition("@")
        if (
            self._managed_group_domain
            and local_part.startswith("sg-")
            and domain != self._managed_group_domain
        ):
            return OperationResult.permanent_error(
                message="Managed directory group email does not match configured domain",
                error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH",
            )

        provider_group_id = str(item.get("id") or "").strip()
        if not provider_group_id:
            return OperationResult.permanent_error(
                message="Managed directory group is missing provider group ID",
                error_code="DIRECTORY_GROUP_ID_REQUIRED",
            )

        return OperationResult.success(
            data={
                "group": DirectoryGroup(
                    group_email=group_email,
                    group_slug=local_part,
                    provider_group_id=provider_group_id,
                    name=item.get("name"),
                    description=item.get("description"),
                    provider="google",
                )
            }
        )

    def warmup(self) -> OperationResult:
        """Validate connectivity by fetching the configured customer.

        Returns:
            OperationResult: success when the API responds successfully.
        """
        log = logger.bind(provider="google", operation="warmup")
        log.info("directory_warmup_started")
        result = self._directory.health_check()
        if result.is_success:
            log.info("directory_warmup_completed")
        else:
            log.error("directory_warmup_failed", error=result.message)
        return result

    def health_check(self) -> OperationResult:
        """Return a fast liveness result without making remote calls.

        Returns:
            OperationResult: always success.
        """
        return OperationResult.success()

    def get_user(self, email: str) -> OperationResult:
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
            return result
        return self._build_directory_user(result.data or {})

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult:
        """Return canonical users matching a query."""

        if limit <= 0:
            return OperationResult.success(data={"users": []})

        list_kwargs: dict[str, Any] = {"maxResults": limit}
        if query:
            list_kwargs["query"] = query

        result = self._directory.list_users(**list_kwargs)
        if not result.is_success:
            return result

        users = []
        for item in (result.data or [])[:limit]:
            user_result = self._build_directory_user(item)
            if not user_result.is_success:
                return user_result

            user_data = user_result.data if isinstance(user_result.data, dict) else {}
            user = user_data.get("user")
            if user is None:
                return OperationResult.permanent_error(
                    message="Directory user mapping returned no canonical user",
                    error_code="DIRECTORY_USER_MAPPING_INVALID",
                )
            users.append(user)

        return OperationResult.success(data={"users": users})

    def get_group_members(self, group_key: str) -> OperationResult:
        """Return the member list for a group.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.

        Returns:
            OperationResult: success with data={"members": list[DirectoryMember]}.
        """
        result = self._directory.list_members(self._normalize_email(group_key))
        if not result.is_success:
            return result

        members = [
            self._build_directory_member(item)
            for item in (result.data or [])
            if item.get("email")
        ]
        return OperationResult.success(data={"members": members})

    def check_membership(self, group_key: str, user_email: str) -> OperationResult:
        """Check whether a user is a member of a group.

        Fetches all members and performs a case-insensitive email comparison
        locally to avoid a separate get-member API call.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.
            user_email: User email to check.

        Returns:
            OperationResult: success with data={"membership": MembershipCheckResult}.
                Returns the error result unchanged when list_members fails.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)

        result = self._directory.list_members(normalized_group)
        if not result.is_success:
            return result

        is_member = any(
            self._normalize_email(str(item.get("email") or "")) == normalized_user_email
            for item in (result.data or [])
        )
        membership = MembershipCheckResult(
            group_email=normalized_group,
            group_slug=normalized_group.split("@", 1)[0],
            provider_group_id=None,
            user_email=normalized_user_email,
            is_member=is_member,
        )
        return OperationResult.success(data={"membership": membership})

    def list_groups(self, query: str) -> OperationResult:
        """List groups matching a query string.

        Args:
            query: IDP-specific query string passed to the Directory API.

        Returns:
            OperationResult: success with data={"groups": list[DirectoryGroup]}.
        """
        result = self._directory.list_groups(query=query)
        if not result.is_success:
            return result

        groups = []
        for item in result.data or []:
            group_result = self._build_directory_group(item)
            if not group_result.is_success:
                return group_result

            group_data = (
                group_result.data if isinstance(group_result.data, dict) else {}
            )
            group = group_data.get("group")
            if group is not None:
                groups.append(group)

        return OperationResult.success(data={"groups": groups})
