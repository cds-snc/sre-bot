"""Google Workspace implementation of DirectoryProvider."""

from typing import Any, TypeVar

import structlog

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.configuration.infrastructure import DirectorySettings
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
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
        self._managed_group_domain = directory_settings.managed_group_domain.strip().lower()
        self._managed_group_prefix = directory_settings.managed_group_prefix.strip().lower()
        self._logger = logger.bind(provider="google")

    def _normalize_email(self, value: str) -> str:
        """Normalize email-form identifiers used by the shared contract.

        Group-key values that do not contain ``@`` are treated as
        managed-group slugs and composed into ``{slug}@{domain}`` when
        ``DIRECTORY_MANAGED_GROUP_DOMAIN`` is configured.
        """
        normalized = value.strip().lower()
        if normalized and "@" not in normalized and self._managed_group_domain:
            return f"{normalized}@{self._managed_group_domain}"
        return normalized

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

    def _extract_managed_group_email(self, item: dict[str, Any]) -> str:
        """Return the canonical managed-group email, preferring managed-prefix aliases."""

        primary_email = self._extract_email(item, "email", "groupEmail")
        aliases = self._extract_group_aliases(item)

        if self._managed_group_prefix:
            for alias in aliases:
                local_part, _, domain = alias.partition("@")
                if not local_part.startswith(self._managed_group_prefix):
                    continue
                if self._managed_group_domain and domain != self._managed_group_domain:
                    continue
                return alias

        return primary_email

    def _managed_group_query_prefix(self, query: str) -> str | None:
        """Return a managed-group prefix for alias-aware discovery queries.

        Returns a prefix string when the query looks like a managed-group prefix
        search (triggering a full-list + client-side alias filter instead of an
        email-field query).  Returns ``None`` when no prefix is configured or the
        query does not match the configured prefix.
        """
        if not self._managed_group_prefix:
            return None
        normalized_query = query.strip().lower()
        if not normalized_query:
            return None
        if ":" not in normalized_query and "=" not in normalized_query:
            return normalized_query if normalized_query.startswith(self._managed_group_prefix) else None
        if normalized_query.startswith("email:") and normalized_query.endswith("*"):
            prefix = normalized_query[len("email:") : -1]
            return prefix if prefix.startswith(self._managed_group_prefix) else None
        return None

    def _matches_managed_group_prefix(self, item: dict[str, Any], prefix: str) -> bool:
        """Return whether the group's primary email or aliases match a prefix."""

        candidates = [self._extract_email(item, "email", "groupEmail")]
        candidates.extend(self._extract_group_aliases(item))
        normalized_prefix = prefix.strip().lower()
        return any(candidate.startswith(normalized_prefix) for candidate in candidates)

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
            member_type=(str(item.get("type") or "").strip().upper() or None),
            role=item.get("role"),
            provider="google",
        )

    def _build_directory_group(self, item: dict[str, Any]) -> OperationResult[DirectoryGroup | None]:
        """Convert a Google group record into a canonical directory group."""

        group_email = self._extract_managed_group_email(item)
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

    def get_user(self, email: str) -> OperationResult[DirectoryUser]:
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

        return OperationResult.success(data=user_result.data)

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult[list[DirectoryUser]]:
        """Return canonical users matching a query."""

        if limit <= 0:
            return OperationResult.success(data=[])

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

        return OperationResult.success(data=users)

    def get_group_members(
        self,
        group_key: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[list[DirectoryMember]]:
        """Return the member list for a group.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.
            include_member_types: Optional set of member types to include
                (for example {"USER"}, {"GROUP"}, or both). Defaults to no
                filtering.

        Returns:
            OperationResult: success with the DirectoryMember list for the group.
        """
        result = self._directory.list_members(
            self._normalize_email(group_key),
            includeDerivedMembership=True,
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

        Uses the Google Admin batch API so cost is one network round-trip
        regardless of the number of groups.

        Args:
            group_keys: Canonical managed-group emails — normalised to lowercase.
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). Defaults to no filtering.

        Returns:
            OperationResult: success with a dict mapping group_key to
            DirectoryMember list.
        """
        if not group_keys:
            return OperationResult.success(data={})

        normalized_keys = [self._normalize_email(k) for k in group_keys]
        result = self._directory.get_batch_group_members(normalized_keys)
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, dict):
            return OperationResult.permanent_error(
                message="Batch directory members payload is not a dict",
                error_code="DIRECTORY_BATCH_MEMBERS_PAYLOAD_INVALID",
            )

        allowed_member_types = None
        if include_member_types is not None:
            allowed_member_types = {str(t).strip().upper() for t in include_member_types if str(t).strip()}
            if not allowed_member_types:
                return OperationResult.permanent_error(
                    message="include_member_types must contain at least one type",
                    error_code="DIRECTORY_MEMBER_TYPES_INVALID",
                )

        batch_members: dict[str, list[DirectoryMember]] = {}
        for group_key, raw_members in result.data.items():
            members: list[DirectoryMember] = []
            if isinstance(raw_members, list):
                for item in raw_members:
                    if not isinstance(item, dict):
                        continue
                    member_type = str(item.get("type") or "").strip().upper()
                    if allowed_member_types is not None and member_type and member_type not in allowed_member_types:
                        continue
                    member = self._build_directory_member(item)
                    if member is not None:
                        members.append(member)
            batch_members[group_key] = members

        return OperationResult.success(data=batch_members)

    def get_group(self, group_key: str) -> OperationResult[DirectoryGroup]:
        """Return a canonical managed group by key.

        Args:
            group_key: Canonical managed-group email or managed-group slug.
                Slugs are composed into canonical email form using
                ``DIRECTORY_MANAGED_GROUP_DOMAIN``.

        Returns:
            OperationResult: success with the canonical DirectoryGroup.
        """
        normalized_group_key = self._normalize_email(group_key)
        result = self._directory.get_group(normalized_group_key)
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, dict):
            return OperationResult.permanent_error(
                message="Directory group payload is not a dict",
                error_code="DIRECTORY_GROUP_PAYLOAD_INVALID",
            )

        group_result = self._build_directory_group(result.data)
        if not group_result.is_success:
            return self._typed_error(group_result)

        if group_result.data is None:
            return OperationResult.permanent_error(
                message="Managed directory group is missing provider-returned email",
                error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
            )

        return OperationResult.success(data=group_result.data)

    def add_group_member(
        self,
        group_key: str,
        user_email: str,
        role: str = "MEMBER",
    ) -> OperationResult[DirectoryMember]:
        """Add a membership to a managed group.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.
            user_email: User email to add — normalised to lowercase.
            role: Membership role hint (default: MEMBER, valid values: MEMBER, MANAGER, OWNER).

        Returns:
            OperationResult: success with the added DirectoryMember.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)
        normalized_role = role.strip().upper() if role.strip() else "MEMBER"

        result = self._directory.add_member(
            normalized_group,
            body={
                "email": normalized_user_email,
                "role": normalized_role,
            },
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
        """Remove a membership from a managed group.

        Args:
            group_key: Canonical managed-group email — normalised to lowercase.
            user_email: User email to remove — normalised to lowercase.

        Returns:
            OperationResult: success with no payload.
        """
        normalized_group = self._normalize_email(group_key)
        normalized_user_email = self._normalize_email(user_email)

        result = self._directory.remove_member(
            normalized_group,
            normalized_user_email,
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
            group_key: Canonical managed-group email — normalised to lowercase.
            user_email: User email to check.

        Returns:
            OperationResult: success with the MembershipCheckResult.
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
        return OperationResult.success(data=membership)

    def list_groups(self, query: str) -> OperationResult[list[DirectoryGroup]]:
        """List groups matching a Google Admin Directory query.

        Args:
            query: Google Admin Directory search clause(s).  Bare strings
                without a field operator are translated to ``email:{query}*``.
                Queries containing ``:`` or ``=`` are passed through unchanged.

        Returns:
            OperationResult: success with the matching DirectoryGroup list.
        """
        managed_prefix = self._managed_group_query_prefix(query)
        if managed_prefix is not None:
            self._logger.info(
                "listing_groups_alias_aware",
                query=query,
                managed_prefix=managed_prefix,
            )
            result = self._directory.list_groups()
        else:
            google_query = f"email:{query}*" if ":" not in query and "=" not in query else query
            result = self._directory.list_groups(query=google_query)
        if not result.is_success:
            return self._typed_error(result)

        if not isinstance(result.data, list):
            return OperationResult.permanent_error(
                message="Directory groups payload is not a list",
                error_code="DIRECTORY_GROUPS_PAYLOAD_INVALID",
            )

        raw_groups = result.data
        if managed_prefix is not None:
            raw_groups = [
                item for item in raw_groups if isinstance(item, dict) and self._matches_managed_group_prefix(item, managed_prefix)
            ]

        groups: list[DirectoryGroup] = []
        for item in raw_groups:
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

        return OperationResult.success(data=groups)

    def get_user_groups(self, user_email: str) -> OperationResult[list[DirectoryGroup]]:
        """Return all managed groups the user is a direct member of.

        Uses ``groups.list(userKey=...)`` — the inverse group lookup — to fetch
        every group the user belongs to in a single paginated call instead of
        calling ``hasMember`` once per candidate group.

        Only groups whose email matches the configured managed-group domain are
        included in the result, so callers can safely compare ``group_slug``
        values against effective policy slugs without domain-filtering.

        Args:
            user_email: Canonical user email, normalised to lowercase.

        Returns:
            OperationResult: success with the list of managed DirectoryGroup
            the user belongs to.
        """
        log = self._logger.bind(operation="get_user_groups", user_email=user_email)
        normalized_email = self._normalize_email(user_email)
        result = self._directory.list_user_groups(normalized_email)
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

            group_result = self._build_directory_group(item)
            if not group_result.is_success:
                return self._typed_error(group_result)

            if group_result.data is not None:
                groups.append(group_result.data)

        return OperationResult.success(data=groups)
