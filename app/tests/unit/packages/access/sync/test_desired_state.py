"""Unit tests for DirectoryMembershipBuilder's ManagedGroupPolicy cut-over (TASK-76.3).

Covers the feature-side managed-group decisions the DirectoryProvider no longer
makes: canonical email/slug resolution, managed-domain filtering, and group-key
composition. Uses a Protocol-conformant DirectoryProvider fake per
decisions/testing.md — never MagicMock.
"""

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import EntitlementRule
from packages.access.common.group_policy import ManagedGroupPolicy
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.policies import EffectivePlatformPolicy

# ---------------------------------------------------------------------------
# Fakes and factories
# ---------------------------------------------------------------------------


class FakeDirectory:
    """Protocol-conformant DirectoryProvider double recording its call keys."""

    def __init__(
        self,
        groups: dict[str, DirectoryGroup] | None = None,
        user_groups: OperationResult | None = None,
        list_groups_result: OperationResult | None = None,
        members: dict[str, list[DirectoryMember]] | None = None,
        is_member: bool = True,
    ) -> None:
        self._groups = groups or {}
        self._user_groups = user_groups or OperationResult.success(data=[])
        self._list_groups_result = list_groups_result or OperationResult.success(data=[])
        self._members = members or {}
        self._is_member = is_member
        self.get_group_keys: list[str] = []
        self.list_groups_queries: list[str] = []
        self.check_membership_keys: list[str] = []

    def get_group(self, group_key: str) -> OperationResult:
        self.get_group_keys.append(group_key)
        group = self._groups.get(group_key)
        if group is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"not found: {group_key}",
                error_code="GROUP_NOT_FOUND",
            )
        return OperationResult.success(data=group)

    def list_groups(self, query: str = "", limit: int | None = None) -> OperationResult:
        self.list_groups_queries.append(query)
        return self._list_groups_result

    def get_user_groups(self, user_email: str) -> OperationResult:
        return self._user_groups

    def check_membership(self, group_key: str, user_email: str) -> OperationResult:
        self.check_membership_keys.append(group_key)
        return OperationResult.success(
            data=MembershipCheckResult(
                group_email=group_key,
                group_slug=group_key.partition("@")[0],
                provider_group_id="gid-authn",
                user_email=user_email,
                is_member=self._is_member,
            )
        )

    def get_group_members(
        self,
        group_key: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult:
        return OperationResult.success(data=self._members.get(group_key, []))

    def get_group_members_batch(
        self,
        group_keys: list[str],
        include_member_types: set[str] | None = None,
    ) -> OperationResult:
        return OperationResult.success(data={key: self._members.get(key, []) for key in group_keys})

    # Unused surface — present so the fake satisfies the full protocol.
    def warmup(self) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success()

    def health_check(self) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success()

    def get_user(self, email: str) -> OperationResult:  # pragma: no cover - unused
        raise NotImplementedError

    def list_users(self, query: str = "", limit: int | None = None) -> OperationResult:  # pragma: no cover - unused
        raise NotImplementedError

    def add_group_member(
        self, group_key: str, user_email: str, role: str = "MEMBER"
    ) -> OperationResult:  # pragma: no cover - unused
        raise NotImplementedError

    def remove_group_member(self, group_key: str, user_email: str) -> OperationResult:  # pragma: no cover - unused
        raise NotImplementedError

    def list_groups_with_members(
        self,
        query: str = "",
        limit: int | None = None,
        include_member_types: set[str] | None = None,
    ) -> OperationResult:  # pragma: no cover - unused
        raise NotImplementedError


def make_policy() -> ManagedGroupPolicy:
    return ManagedGroupPolicy(prefix="sg-", domain="example.com")


def make_group(
    slug: str,
    email: str | None = None,
    aliases: tuple[str, ...] = (),
    provider_group_id: str = "gid-001",
) -> DirectoryGroup:
    return DirectoryGroup(
        group_email=email if email is not None else f"{slug}@example.com",
        group_slug=slug,
        provider_group_id=provider_group_id,
        aliases=aliases,
    )


def make_rule(slug: str, entitlement_id: str) -> EntitlementRule:
    return EntitlementRule(group_slug=slug, entitlement_id=entitlement_id)


def make_effective(rules: list[EntitlementRule] | None = None) -> EffectivePlatformPolicy:
    return EffectivePlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_removal_mode="delete",
        entitlement_rules=rules or [],
    )


def make_builder(directory: FakeDirectory) -> DirectoryMembershipBuilder:
    return DirectoryMembershipBuilder(directory, make_policy())  # type: ignore[arg-type]


AUTHN_GROUP = make_group("sg-aws-authn", provider_group_id="gid-authn")


@pytest.mark.unit
def test_fake_directory_should_conform_to_directory_provider_protocol():
    assert isinstance(FakeDirectory(), DirectoryProvider)


# ---------------------------------------------------------------------------
# build_user_state_from_effective — list-shaped: omit out-of-domain groups
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_user_state_should_omit_out_of_domain_group_from_user_groups():
    directory = FakeDirectory(
        groups={"sg-aws-authn@example.com": AUTHN_GROUP},
        user_groups=OperationResult.success(
            data=[
                make_group("sg-aws-admins"),
                make_group("sg-aws-readers", email="sg-aws-readers@other-tenant.com"),
            ]
        ),
    )
    builder = make_builder(directory)
    effective = make_effective(
        [
            make_rule("sg-aws-admins", "admins"),
            make_rule("sg-aws-readers", "readers"),
        ]
    )

    result = builder.build_user_state_from_effective("user@example.com", effective)

    assert result.is_success
    assert result.data is not None
    assert [rule.entitlement_id for rule in result.data.required_entitlements] == ["admins"]


@pytest.mark.unit
def test_build_user_state_should_match_rules_on_alias_preferred_canonical_slug():
    directory = FakeDirectory(
        groups={"sg-aws-authn@example.com": AUTHN_GROUP},
        user_groups=OperationResult.success(
            data=[
                make_group(
                    "legacy-admins",
                    email="legacy-admins@example.com",
                    aliases=("sg-aws-admins@example.com",),
                )
            ]
        ),
    )
    builder = make_builder(directory)
    effective = make_effective([make_rule("sg-aws-admins", "admins")])

    result = builder.build_user_state_from_effective("user@example.com", effective)

    assert result.is_success
    assert result.data is not None
    assert [rule.entitlement_id for rule in result.data.required_entitlements] == ["admins"]


# ---------------------------------------------------------------------------
# _check_group_membership — get-shaped: composed key and domain-mismatch error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_user_state_should_fetch_authn_group_by_composed_group_key():
    directory = FakeDirectory(groups={"sg-aws-authn@example.com": AUTHN_GROUP})
    builder = make_builder(directory)

    builder.build_user_state_from_effective("user@example.com", make_effective())

    assert directory.get_group_keys == ["sg-aws-authn@example.com"]


@pytest.mark.unit
def test_build_user_state_should_error_when_authn_group_is_outside_managed_domain():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": make_group(
                "sg-aws-authn",
                email="sg-aws-authn@other-tenant.com",
                provider_group_id="gid-authn",
            )
        }
    )
    builder = make_builder(directory)

    result = builder.build_user_state_from_effective("user@example.com", make_effective())

    assert not result.is_success
    assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"


@pytest.mark.unit
def test_build_user_state_should_check_membership_against_canonical_alias_email():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": make_group(
                "legacy-authn",
                email="legacy-authn@example.com",
                aliases=("sg-aws-authn@example.com",),
                provider_group_id="gid-authn",
            )
        }
    )
    builder = make_builder(directory)

    builder.build_user_state_from_effective("user@example.com", make_effective())

    assert directory.check_membership_keys == ["sg-aws-authn@example.com"]


# ---------------------------------------------------------------------------
# build_platform_state_from_effective — get-shaped: propagate domain mismatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_platform_state_should_fetch_groups_by_composed_group_key():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": AUTHN_GROUP,
            "sg-aws-admins@example.com": make_group("sg-aws-admins"),
        },
        members={"sg-aws-authn@example.com": [DirectoryMember(email="user@example.com")]},
    )
    builder = make_builder(directory)

    result = builder.build_platform_state_from_effective(make_effective([make_rule("sg-aws-admins", "admins")]))

    assert result.is_success
    assert directory.get_group_keys == [
        "sg-aws-authn@example.com",
        "sg-aws-admins@example.com",
    ]


@pytest.mark.unit
def test_build_platform_state_should_error_when_authn_group_is_outside_managed_domain():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": make_group(
                "sg-aws-authn",
                email="sg-aws-authn@other-tenant.com",
                provider_group_id="gid-authn",
            )
        }
    )
    builder = make_builder(directory)

    result = builder.build_platform_state_from_effective(make_effective())

    assert not result.is_success
    assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"


@pytest.mark.unit
def test_build_platform_state_should_error_when_rule_group_is_outside_managed_domain():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": AUTHN_GROUP,
            "sg-aws-admins@example.com": make_group(
                "sg-aws-admins",
                email="sg-aws-admins@other-tenant.com",
            ),
        },
        members={"sg-aws-authn@example.com": [DirectoryMember(email="user@example.com")]},
    )
    builder = make_builder(directory)

    result = builder.build_platform_state_from_effective(make_effective([make_rule("sg-aws-admins", "admins")]))

    assert not result.is_success
    assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"


@pytest.mark.unit
def test_build_platform_state_should_skip_not_found_rule_group_without_error():
    directory = FakeDirectory(
        groups={"sg-aws-authn@example.com": AUTHN_GROUP},
        members={"sg-aws-authn@example.com": [DirectoryMember(email="user@example.com")]},
    )
    builder = make_builder(directory)

    result = builder.build_platform_state_from_effective(make_effective([make_rule("sg-aws-admins", "admins")]))

    assert result.is_success
    assert result.data is not None
    assert result.data.desired_members_by_entitlement == {}


@pytest.mark.unit
def test_build_platform_state_should_batch_members_by_canonical_alias_email():
    directory = FakeDirectory(
        groups={
            "sg-aws-authn@example.com": AUTHN_GROUP,
            "sg-aws-admins@example.com": make_group(
                "legacy-admins",
                email="legacy-admins@example.com",
                aliases=("sg-aws-admins@example.com",),
            ),
        },
        members={
            "sg-aws-authn@example.com": [DirectoryMember(email="user@example.com")],
            "sg-aws-admins@example.com": [DirectoryMember(email="user@example.com")],
        },
    )
    builder = make_builder(directory)

    result = builder.build_platform_state_from_effective(make_effective([make_rule("sg-aws-admins", "admins")]))

    assert result.is_success
    assert result.data is not None
    assert result.data.desired_members_by_entitlement == {"admins": {"user@example.com"}}


# ---------------------------------------------------------------------------
# discover_group_slugs — list-shaped: generic listing plus client-side policy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_discover_group_slugs_should_exclude_foreign_platform_group(make_runtime_config):
    directory = FakeDirectory(
        list_groups_result=OperationResult.success(data=[make_group("sg-aws-admins"), make_group("sg-gcp-admins")])
    )
    builder = make_builder(directory)

    result = builder.discover_group_slugs(make_runtime_config(), "aws")

    assert result.is_success
    assert result.data == {"sg-aws-admins"}
    assert directory.list_groups_queries == [""]


@pytest.mark.unit
def test_discover_group_slugs_should_omit_out_of_domain_group_without_failing(make_runtime_config):
    directory = FakeDirectory(
        list_groups_result=OperationResult.success(
            data=[
                make_group("sg-aws-admins"),
                make_group("sg-aws-external", email="sg-aws-external@other-tenant.com"),
            ]
        )
    )
    builder = make_builder(directory)

    result = builder.discover_group_slugs(make_runtime_config(), "aws")

    assert result.is_success
    assert result.data == {"sg-aws-admins"}


@pytest.mark.unit
def test_discover_group_slugs_should_use_alias_preferred_canonical_slug(make_runtime_config):
    directory = FakeDirectory(
        list_groups_result=OperationResult.success(
            data=[
                make_group(
                    "legacy-admins",
                    email="legacy-admins@example.com",
                    aliases=("sg-aws-admins@example.com",),
                )
            ]
        )
    )
    builder = make_builder(directory)

    result = builder.discover_group_slugs(make_runtime_config(), "aws")

    assert result.is_success
    assert result.data == {"sg-aws-admins"}


@pytest.mark.unit
def test_discover_group_slugs_should_propagate_directory_failure(make_runtime_config):
    directory = FakeDirectory(
        list_groups_result=OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="idp unavailable",
            error_code="DIRECTORY_UNAVAILABLE",
        )
    )
    builder = make_builder(directory)

    result = builder.discover_group_slugs(make_runtime_config(), "aws")

    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "DIRECTORY_UNAVAILABLE"
    assert result.data is None
