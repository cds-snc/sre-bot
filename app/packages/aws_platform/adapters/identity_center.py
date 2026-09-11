"""AWS Identity Center (identitystore) adapter for the legacy modules and jobs.

Holds typed boto3 identitystore clients built by ``get_aws_client``, calls the
SDK directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

Clients carry eagerly assumed STS credentials, so callers build the adapter
with :func:`build_identity_center_adapter` at function entry, never at import.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_identitystore.client import IdentityStoreClient

logger = structlog.get_logger()

type GroupFilter = Callable[[dict[str, Any]], bool]
type _PaginatorName = Literal["list_users", "list_groups", "list_group_memberships"]

_GROUP_PROJECTION_KEYS = ("GroupId", "DisplayName", "Description", "IdentityStoreId")
_DESCRIBE_USER_DROPPED_KEYS = ("ResponseMetadata", "IdentityStoreId")


class IdentityCenterAdapter:
    """Identity Store operations returning ``OperationResult``.

    Args:
        identitystore: standard-retry client for reads, gets and deletes.
        identitystore_no_retry: retries-disabled client for the non-idempotent
            creates (``CreateUser`` and ``CreateGroupMembership`` have no client
            token, so an SDK retry after a timeout could re-send a create that
            already succeeded).
        identity_store_id: ``IdentityStoreId`` sent on every call.
    """

    def __init__(
        self,
        identitystore: IdentityStoreClient,
        identitystore_no_retry: IdentityStoreClient,
        identity_store_id: str,
    ) -> None:
        self._identitystore = identitystore
        self._identitystore_no_retry = identitystore_no_retry
        self._identity_store_id = identity_store_id

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_identity_store_operation_failed",
            operation=operation,
            status=status.value,
            error_code=error_code,
        )
        return OperationResult.error(
            status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="aws",
            operation=operation,
        )

    def _call[T](self, operation: str, fn: Callable[[], T]) -> OperationResult[T]:
        """Run one SDK call, classifying ClientError/BotoCoreError; anything else propagates."""
        try:
            return OperationResult.success(data=fn(), provider="aws", operation=operation)
        except (ClientError, BotoCoreError) as exc:
            return self._map_sdk_exception(operation, exc)

    def _paginate(
        self, paginator_name: _PaginatorName, response_key: str, **kwargs: Any
    ) -> OperationResult[list[dict[str, Any]]]:
        """Flatten every page of a paginated operation into one list."""

        def collect() -> list[dict[str, Any]]:
            paginator = self._identitystore.get_paginator(paginator_name)
            items: list[dict[str, Any]] = []
            for page in paginator.paginate(IdentityStoreId=self._identity_store_id, **kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    # -- health -------------------------------------------------------------

    def healthcheck(self) -> OperationResult[bool]:
        """Healthy iff a single-page ListUsers succeeds; an empty store is healthy."""

        def probe() -> bool:
            self._identitystore.list_users(IdentityStoreId=self._identity_store_id, MaxResults=1)
            return True

        return self._call("healthcheck", probe)

    # -- users --------------------------------------------------------------

    def create_user(self, email: str, first_name: str, family_name: str) -> OperationResult[str]:
        """Create a user keyed by email; returns the new UserId. Sent without SDK retries."""
        return self._call(
            "create_user",
            lambda: self._identitystore_no_retry.create_user(
                IdentityStoreId=self._identity_store_id,
                UserName=email,
                Emails=[{"Value": email, "Type": "WORK", "Primary": True}],
                Name={"GivenName": first_name, "FamilyName": family_name},
                DisplayName=f"{first_name} {family_name}",
            )["UserId"],
        )

    def delete_user(self, user_id: str) -> OperationResult[bool]:
        """Delete a user by id."""

        def delete() -> bool:
            self._identitystore.delete_user(IdentityStoreId=self._identity_store_id, UserId=user_id)
            return True

        return self._call("delete_user", delete)

    def get_user_id(self, user_name: str) -> OperationResult[str]:
        """Resolve a UserId from its userName (NOT_FOUND when no user matches)."""
        return self._call(
            "get_user_id",
            lambda: self._identitystore.get_user_id(
                IdentityStoreId=self._identity_store_id,
                # AttributeValue is a boto3 "document" type (any JSON scalar); the generated stub
                # over-narrows it to Mapping[str, Any], as packages/access notes.
                AlternateIdentifier={"UniqueAttribute": {"AttributePath": "userName", "AttributeValue": user_name}},  # type: ignore[typeddict-item]
            )["UserId"],
        )

    def describe_user(self, user_id: str) -> OperationResult[dict[str, Any]]:
        """Return the user's attributes without the response envelope keys."""

        def describe() -> dict[str, Any]:
            response = self._identitystore.describe_user(IdentityStoreId=self._identity_store_id, UserId=user_id)
            return {key: value for key, value in response.items() if key not in _DESCRIBE_USER_DROPPED_KEYS}

        return self._call("describe_user", describe)

    def list_users(self, filters: list[dict[str, str]] | None = None) -> OperationResult[list[dict[str, Any]]]:
        """List every user, optionally narrowed by Identity Store Filters."""
        kwargs: dict[str, Any] = {"Filters": filters} if filters is not None else {}
        return self._paginate("list_users", "Users", **kwargs)

    # -- groups -------------------------------------------------------------

    def get_group_id(self, group_name: str) -> OperationResult[str]:
        """Resolve a GroupId from its displayName (NOT_FOUND when no group matches)."""
        return self._call(
            "get_group_id",
            lambda: self._identitystore.get_group_id(
                IdentityStoreId=self._identity_store_id,
                # AttributeValue is a boto3 "document" type (any JSON scalar); the generated stub
                # over-narrows it to Mapping[str, Any], as packages/access notes.
                AlternateIdentifier={"UniqueAttribute": {"AttributePath": "displayName", "AttributeValue": group_name}},  # type: ignore[typeddict-item]
            )["GroupId"],
        )

    def list_groups(self, filters: list[dict[str, str]] | None = None) -> OperationResult[list[dict[str, Any]]]:
        """List every group, optionally narrowed by Identity Store Filters."""
        kwargs: dict[str, Any] = {"Filters": filters} if filters is not None else {}
        return self._paginate("list_groups", "Groups", **kwargs)

    # -- memberships --------------------------------------------------------

    def create_group_membership(self, group_id: str, user_id: str) -> OperationResult[str]:
        """Add a user to a group; returns the MembershipId. Sent without SDK retries."""
        return self._call(
            "create_group_membership",
            lambda: self._identitystore_no_retry.create_group_membership(
                IdentityStoreId=self._identity_store_id,
                GroupId=group_id,
                MemberId={"UserId": user_id},
            )["MembershipId"],
        )

    def delete_group_membership(self, membership_id: str) -> OperationResult[bool]:
        """Remove a group membership by id."""

        def delete() -> bool:
            self._identitystore.delete_group_membership(IdentityStoreId=self._identity_store_id, MembershipId=membership_id)
            return True

        return self._call("delete_group_membership", delete)

    def get_group_membership_id(self, group_id: str, user_id: str) -> OperationResult[str]:
        """Resolve the MembershipId linking a user to a group."""
        return self._call(
            "get_group_membership_id",
            lambda: self._identitystore.get_group_membership_id(
                IdentityStoreId=self._identity_store_id,
                GroupId=group_id,
                MemberId={"UserId": user_id},
            )["MembershipId"],
        )

    def list_group_memberships(self, group_id: str) -> OperationResult[list[dict[str, Any]]]:
        """List every membership of a group."""
        return self._paginate("list_group_memberships", "GroupMemberships", GroupId=group_id)

    def list_groups_with_memberships(
        self,
        groups_filters: Iterable[GroupFilter] | None = None,
        tolerate_errors: bool = False,
    ) -> OperationResult[list[dict[str, Any]]]:
        """Join groups, their memberships and the member user records.

        Groups are filtered by the given callables and projected to GroupId,
        DisplayName, Description and IdentityStoreId; each membership's
        ``MemberId`` is enriched with the matching user record. A group whose
        membership listing fails is logged and skipped. A membership whose user
        is unknown drops the group unless ``tolerate_errors`` is set. Groups
        without memberships are omitted. A failed ListGroups or ListUsers is
        returned as the operation's own failure.
        """
        log = logger.bind(operation="list_groups_with_memberships", tolerate_errors=tolerate_errors)
        groups_result = self.list_groups()
        if not groups_result.is_success:
            return groups_result
        groups = groups_result.data or []
        log.info("aws_identity_store_groups_fetched", count=len(groups))
        if not groups:
            return OperationResult.success(data=[], provider="aws", operation="list_groups_with_memberships")

        if groups_filters is not None:
            original_count = len(groups)
            for group_filter in groups_filters:
                groups = [group for group in groups if group_filter(group)]
            log.info("aws_identity_store_groups_filtered", original_count=original_count, filtered_count=len(groups))

        projected_groups = [{key: value for key, value in group.items() if key in _GROUP_PROJECTION_KEYS} for group in groups]

        users_result = self.list_users()
        if not users_result.is_success:
            return users_result
        users_by_id: dict[str, Mapping[str, Any]] = {user["UserId"]: user for user in users_result.data or []}
        log.info("aws_identity_store_users_fetched", count=len(users_by_id))

        groups_with_memberships: list[dict[str, Any]] = []
        for group in projected_groups:
            group_id = group.get("GroupId", "")
            group_name = group.get("DisplayName", "unknown")
            memberships_result = self.list_group_memberships(group_id)
            if not memberships_result.is_success:
                log.error(
                    "aws_identity_store_group_memberships_error",
                    group_id=group_id,
                    group_name=group_name,
                    status=memberships_result.status.value,
                    error_code=memberships_result.error_code,
                )
                continue

            memberships = memberships_result.data or []
            error_occurred = False
            for membership in memberships:
                member_user_id = membership["MemberId"]["UserId"]
                member_details = users_by_id.get(member_user_id)
                if member_details is None:
                    log.warning(
                        "aws_identity_store_member_error",
                        group_id=group_id,
                        group_name=group_name,
                        member_id=member_user_id,
                    )
                    error_occurred = True
                    if not tolerate_errors:
                        break
                    continue
                membership["MemberId"].update(member_details)

            if memberships and (not error_occurred or tolerate_errors):
                group["GroupMemberships"] = memberships
                groups_with_memberships.append(group)

        log.info("aws_identity_store_operation_complete", count=len(groups_with_memberships))
        return OperationResult.success(data=groups_with_memberships, provider="aws", operation="list_groups_with_memberships")


def build_identity_center_adapter() -> IdentityCenterAdapter:
    """Build the adapter from AWS settings: org role for identitystore, IdentityStoreId from INSTANCE_ID.

    Two clients are built per call: a standard-retry client and a
    retries-disabled one for the non-idempotent creates.
    """
    settings = get_aws_settings()
    role_arn = settings.SERVICE_ROLE_MAP.get("identitystore") or None
    identitystore = get_aws_client("identitystore", role_arn=role_arn)
    identitystore_no_retry = get_aws_client("identitystore", role_arn=role_arn, retries=False)
    return IdentityCenterAdapter(identitystore, identitystore_no_retry, settings.INSTANCE_ID)
