"""Contract tests for mode_overrides semantics across access sub-features."""

from dataclasses import dataclass

from infrastructure.directory.models import DirectoryGroup, MembershipCheckResult
from infrastructure.operations import OperationResult
from packages.access.catalog.service import CatalogService
from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
from packages.access.request.policies import check_entitlement_mode
from packages.access.sync.policies import resolve_effective_policy


@dataclass
class _FakeDirectory:
    """Simple deterministic directory stub for catalog checks."""

    groups: list[DirectoryGroup]

    def list_groups(self, query: str) -> OperationResult[list[DirectoryGroup]]:
        return OperationResult.success(data=list(self.groups))

    def check_membership(
        self,
        group_email: str,
        user_email: str,
    ) -> OperationResult[MembershipCheckResult]:
        return OperationResult.success(
            data=MembershipCheckResult(
                group_email=group_email,
                group_slug=group_email.split("@", 1)[0],
                provider_group_id="gid-001",
                user_email=user_email,
                is_member=False,
            )
        )


def _runtime_config(mode_overrides: dict[str, str]) -> AccessRuntimeConfig:
    return AccessRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={
            "aws": PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
                mode_overrides=mode_overrides,  # type: ignore[arg-type]
            )
        },
    )


def _catalog_mode(config: AccessRuntimeConfig) -> tuple[str, bool]:
    service = CatalogService(
        runtime_config=config,
        directory=_FakeDirectory(  # type: ignore[arg-type]
            groups=[
                DirectoryGroup(
                    group_email="sg-aws-admins@example.com",
                    group_slug="sg-aws-admins",
                    provider_group_id="gid-001",
                )
            ]
        ),
        parsers={},
    )
    result = service.list_entitlements(platform="aws", user_email="user@example.com")
    assert result.is_success
    assert result.data is not None
    assert len(result.data) == 1
    entry = result.data[0]
    return entry.mode, entry.requestable


def test_mode_override_contract_token_key_is_consistent_across_request_sync_and_catalog():
    config = _runtime_config(mode_overrides={"admins": "deactivated"})

    request_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="sg-aws-admins",
    )
    effective = resolve_effective_policy(
        config=config,
        platform="aws",
        discovered_slugs={"sg-aws-admins"},
    )
    catalog_mode, requestable = _catalog_mode(config)

    assert request_mode == "deactivated"
    assert effective.entitlement_rules == []
    assert catalog_mode == "deactivated"
    assert requestable is False


def test_mode_override_contract_full_slug_key_is_not_matched():
    """Full slug keys in mode_overrides are NOT matched; token-only keys are canonical."""
    config = _runtime_config(mode_overrides={"sg-aws-admins": "deactivated"})

    request_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="sg-aws-admins",
    )
    effective = resolve_effective_policy(
        config=config,
        platform="aws",
        discovered_slugs={"sg-aws-admins"},
    )
    catalog_mode, requestable = _catalog_mode(config)

    assert request_mode == "sync_managed"
    assert len(effective.entitlement_rules) == 1
    assert catalog_mode == "sync_managed"
    assert requestable is True


def test_mode_override_contract_partial_prefix_not_matched():
    """Partial prefixes like 'aws-' or 'sg-' are NOT matched as tokens."""
    config = _runtime_config(mode_overrides={"aws-admins": "deactivated"})

    request_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="sg-aws-admins",
    )
    effective = resolve_effective_policy(
        config=config,
        platform="aws",
        discovered_slugs={"sg-aws-admins"},
    )

    assert request_mode == "sync_managed"
    assert len(effective.entitlement_rules) == 1


def test_mode_override_contract_multiple_tokens_isolated():
    """Different tokens are isolated; override on one doesn't affect others."""
    config = _runtime_config(
        mode_overrides={
            "admins": "deactivated",
            "developers": "ephemeral",
            "guests": "sync_managed",
        }
    )

    admins_mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-admins")
    devs_mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-developers")
    guests_mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-guests")

    assert admins_mode == "deactivated"
    assert devs_mode == "ephemeral"
    assert guests_mode == "sync_managed"


def test_mode_override_contract_case_insensitivity():
    """Token matching is case-insensitive (slug normalized internally)."""
    config = _runtime_config(mode_overrides={"admins": "deactivated"})

    upper_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="SG-AWS-ADMINS",
    )
    lower_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="sg-aws-admins",
    )
    mixed_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="Sg-Aws-Admins",
    )

    assert upper_mode == "deactivated"
    assert lower_mode == "deactivated"
    assert mixed_mode == "deactivated"


def test_mode_override_contract_sync_excludes_ephemeral_and_deactivated():
    """Sync effective policy excludes ephemeral/deactivated; catalog includes with mode flag."""
    config = _runtime_config(
        mode_overrides={
            "admins": "deactivated",
            "breakglass": "ephemeral",
            "standard": "sync_managed",
        }
    )

    effective = resolve_effective_policy(
        config=config,
        platform="aws",
        discovered_slugs={
            "sg-aws-admins",
            "sg-aws-breakglass",
            "sg-aws-standard",
        },
    )

    tokens = {rule.entitlement_id for rule in effective.entitlement_rules}
    assert tokens == {"standard"}
    assert all(rule.mode == "sync_managed" for rule in effective.entitlement_rules)


def test_mode_override_contract_whitespace_stripped():
    """Token lookup strips whitespace from group slugs."""
    config = _runtime_config(mode_overrides={"admins": "deactivated"})

    with_spaces_mode = check_entitlement_mode(
        config,
        platform="aws",
        group_slug="  sg-aws-admins  ",
    )

    assert with_spaces_mode == "deactivated"
