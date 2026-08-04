"""Unit tests for packages.access.catalog.service."""

import json
from dataclasses import dataclass, field

from infrastructure.directory.models import DirectoryGroup, MembershipCheckResult
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.catalog import providers as catalog_providers
from packages.access.catalog.domain import ParsedEntitlementToken
from packages.access.catalog.service import CatalogService
from packages.access.common.config import (
    AccessRuntimeConfig as AccessSyncRuntimeConfig,
)
from packages.access.common.config import (
    InlineJsonConfigLoader,
    PlatformPolicy,
)

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeDirectory:
    """Stub that lets each test declare its own IDP responses."""

    groups_by_prefix: dict[str, OperationResult] = field(default_factory=dict)
    memberships: dict[str, OperationResult] = field(default_factory=dict)

    def list_groups(self, query: str) -> OperationResult:
        return self.groups_by_prefix.get(
            query,
            OperationResult.success(data=[]),
        )

    def check_membership(self, group_email: str, user_email: str) -> OperationResult:
        return self.memberships.get(
            group_email,
            OperationResult.success(
                data=MembershipCheckResult(
                    group_email=group_email,
                    group_slug="",
                    provider_group_id=None,
                    user_email=user_email,
                    is_member=False,
                )
            ),
        )


class _AlwaysParsedParser:
    """Stub that returns a fixed ParsedEntitlementToken with parsed=True."""

    def parse(self, token: str) -> ParsedEntitlementToken:
        return ParsedEntitlementToken(raw=token, product=token, role="role", parsed=True)


def make_runtime_config(
    platform: str = "aws",
    authn_token: str = "authn",
    mode_overrides: dict | None = None,
    dir_prefix: str = "sg",
    dir_separator: str = "-",
) -> AccessSyncRuntimeConfig:
    return AccessSyncRuntimeConfig(
        dir_prefix=dir_prefix,
        dir_separator=dir_separator,
        platforms={
            platform: PlatformPolicy(
                authn_token=authn_token,
                mode_overrides=mode_overrides or {},
            )
        },
    )


def make_group(
    slug: str = "sg-aws-admin",
    email: str = "sg-aws-admin@example.com",
    provider_group_id: str = "gid-001",
) -> DirectoryGroup:
    return DirectoryGroup(
        group_email=email,
        group_slug=slug,
        provider_group_id=provider_group_id,
    )


def make_service(
    runtime_config=None,
    directory=None,
    parsers=None,
    display_names=None,
):
    cfg = runtime_config or make_runtime_config()
    return CatalogService(
        runtime_config=cfg,
        directory=directory or _FakeDirectory(),
        parsers=parsers or {},
        display_names=display_names,
    )


# ---------------------------------------------------------------------------
# list_platforms — happy paths
# ---------------------------------------------------------------------------


def test_list_platforms_should_return_summary_for_each_configured_platform():
    # Arrange
    cfg = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={
            "aws": PlatformPolicy(authn_token="authn"),
            "gcp": PlatformPolicy(authn_token="authn"),
        },
    )
    service = make_service(runtime_config=cfg)

    # Act
    result = service.list_platforms()

    # Assert
    assert result.is_success
    keys = [p.key for p in result.data]
    assert keys == ["aws", "gcp"]  # sorted


def test_list_platforms_should_use_display_names_when_provided():
    # Arrange
    cfg = make_runtime_config(platform="aws")
    service = make_service(
        runtime_config=cfg,
        display_names={"aws": "Amazon Web Services"},
    )

    # Act
    result = service.list_platforms()

    # Assert
    assert result.is_success
    assert result.data[0].display_name == "Amazon Web Services"


def test_list_platforms_should_fall_back_to_platform_key_as_display_name():
    # Arrange
    service = make_service()

    # Act
    result = service.list_platforms()

    # Assert
    assert result.is_success
    assert result.data[0].display_name == "aws"


def test_list_platforms_should_use_display_name_from_runtime_extensions_via_provider_assembly(
    monkeypatch,
):
    payload = {
        "dir_prefix": "sg",
        "dir_separator": "-",
        "platforms": {
            "aws": {
                "authn_token": "authn",
                "authn_removal_mode": "delete",
                "mode_overrides": {},
            }
        },
        "extensions": {"catalog": {"platform_display_names": {"aws": "Amazon Web Services"}}},
    }
    result = InlineJsonConfigLoader().load(json.dumps(payload))
    assert result.is_success
    assert result.data is not None

    catalog_providers._build_parser_map.cache_clear()
    catalog_providers.get_catalog_service.cache_clear()
    monkeypatch.setattr(
        catalog_providers,
        "get_access_runtime_config",
        lambda: result.data,
    )
    monkeypatch.setattr(
        catalog_providers,
        "get_directory_provider",
        lambda: _FakeDirectory(),
    )

    service = catalog_providers.get_catalog_service()
    platforms = service.list_platforms()

    assert platforms.is_success
    assert platforms.data is not None
    assert platforms.data[0].display_name == "Amazon Web Services"


def test_list_platforms_should_derive_authn_group_slug_from_config():
    # Arrange
    service = make_service()

    # Act
    result = service.list_platforms()

    # Assert
    assert result.is_success
    assert result.data[0].authn_group_slug == "sg-aws-authn"


def test_list_platforms_should_return_empty_list_when_no_platforms_configured():
    # Arrange
    cfg = AccessSyncRuntimeConfig(dir_prefix="sg", platforms={})
    service = make_service(runtime_config=cfg)

    # Act
    result = service.list_platforms()

    # Assert
    assert result.is_success
    assert result.data == []


# ---------------------------------------------------------------------------
# list_entitlements — platform validation
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_not_found_for_unknown_platform():
    # Arrange
    service = make_service()

    # Act
    result = service.list_entitlements(platform="nonexistent", user_email="u@x.com")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.NOT_FOUND
    assert "nonexistent" in (result.message or "").lower()


def test_list_entitlements_should_normalize_platform_key_to_lowercase():
    # Arrange
    directory = _FakeDirectory(groups_by_prefix={"sg-aws-": OperationResult.success(data=[])})
    service = make_service(directory=directory)

    # Act — mixed case
    result = service.list_entitlements(platform="AWS", user_email="u@x.com")

    # Assert — no not_found; platform matched after normalisation
    assert result.is_success


# ---------------------------------------------------------------------------
# list_entitlements — group discovery failure
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_error_when_group_discovery_fails():
    # Arrange
    directory = _FakeDirectory(
        groups_by_prefix={
            "sg-aws-": OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="IDP unavailable",
            )
        }
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.PERMANENT_ERROR


# ---------------------------------------------------------------------------
# list_entitlements — happy path
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_entry_for_each_entitlement_group():
    # Arrange
    groups = [
        make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com"),
        make_group(slug="sg-aws-readonly", email="sg-aws-readonly@example.com"),
    ]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
        memberships={
            "sg-aws-admin@example.com": OperationResult.success(
                data=MembershipCheckResult(
                    group_email="sg-aws-admin@example.com",
                    group_slug="sg-aws-admin",
                    provider_group_id=None,
                    user_email="u@x.com",
                    is_member=True,
                )
            ),
            "sg-aws-readonly@example.com": OperationResult.success(
                data=MembershipCheckResult(
                    group_email="sg-aws-readonly@example.com",
                    group_slug="sg-aws-readonly",
                    provider_group_id=None,
                    user_email="u@x.com",
                    is_member=False,
                )
            ),
        },
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    assert result.is_success
    assert len(result.data) == 2  # authn group is excluded


def test_list_entitlements_should_exclude_authn_group():
    # Arrange
    groups = [
        make_group(slug="sg-aws-authn", email="sg-aws-authn@example.com"),
        make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com"),
    ]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    tokens = [e.token for e in result.data]
    assert "authn" not in tokens
    assert "admin" in tokens


def test_list_entitlements_should_annotate_membership_correctly():
    # Arrange
    groups = [
        make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com"),
    ]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
        memberships={
            "sg-aws-admin@example.com": OperationResult.success(
                data=MembershipCheckResult(
                    group_email="sg-aws-admin@example.com",
                    group_slug="sg-aws-admin",
                    provider_group_id=None,
                    user_email="member@x.com",
                    is_member=True,
                )
            )
        },
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="member@x.com")

    # Assert
    assert result.data[0].already_provisioned is True


def test_list_entitlements_should_set_membership_to_none_when_check_fails():
    # Arrange — membership check returns error
    groups = [make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com")]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
        memberships={"sg-aws-admin@example.com": OperationResult.error(OperationStatus.PERMANENT_ERROR, message="IDP hiccup")},
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert — entry still returned; membership unknown
    assert result.is_success
    assert result.data[0].already_provisioned is None


# ---------------------------------------------------------------------------
# list_entitlements — mode logic
# ---------------------------------------------------------------------------


def test_list_entitlements_should_mark_sync_managed_token_as_requestable():
    # Arrange — no mode override; default is sync_managed
    groups = [make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com")]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    assert result.data[0].mode == "sync_managed"
    assert result.data[0].requestable is True


def test_list_entitlements_should_mark_deactivated_token_as_not_requestable():
    # Arrange
    cfg = make_runtime_config(platform="aws", mode_overrides={"admin": "deactivated"})
    groups = [make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com")]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
    )
    service = make_service(runtime_config=cfg, directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    assert result.data[0].mode == "deactivated"
    assert result.data[0].requestable is False


def test_list_entitlements_should_use_registered_parser_for_platform():
    # Arrange
    groups = [make_group(slug="sg-aws-admin", email="sg-aws-admin@example.com")]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=groups)},
    )
    service = make_service(
        directory=directory,
        parsers={"aws": _AlwaysParsedParser()},
    )

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert — stub parser was used
    assert result.data[0].parsed_token.parsed is True


def test_list_entitlements_should_fall_back_to_fallback_parser_for_unknown_platform():
    # Arrange — platform is "custom"; no parser registered
    cfg = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={"custom": PlatformPolicy(authn_token="authn")},
    )
    groups = [make_group(slug="sg-custom-role1", email="sg-custom-role1@example.com")]
    directory = _FakeDirectory(
        groups_by_prefix={"sg-custom-": OperationResult.success(data=groups)},
    )
    service = make_service(runtime_config=cfg, directory=directory, parsers={})

    # Act
    result = service.list_entitlements(platform="custom", user_email="u@x.com")

    # Assert — FallbackCatalogSlugParser returns parsed=False
    assert result.is_success
    assert result.data[0].parsed_token.parsed is False


def test_list_entitlements_should_return_empty_list_when_no_groups_discovered():
    # Arrange
    directory = _FakeDirectory(
        groups_by_prefix={"sg-aws-": OperationResult.success(data=[])},
    )
    service = make_service(directory=directory)

    # Act
    result = service.list_entitlements(platform="aws", user_email="u@x.com")

    # Assert
    assert result.is_success
    assert result.data == []
