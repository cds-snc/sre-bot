"""Behavior tests for the feature-side managed-group policy (TASK-76.2)."""

import pytest

from infrastructure.directory.models import DirectoryGroup
from packages.access.common.config.settings import AccessRuntimeConfig
from packages.access.common.group_policy import ManagedGroupPolicy

MANAGED_DOMAIN = "example.com"


def make_group(
    group_email: str,
    aliases: tuple[str, ...] = (),
    group_slug: str = "slug",
) -> DirectoryGroup:
    return DirectoryGroup(
        group_email=group_email,
        group_slug=group_slug,
        provider_group_id="gid-1",
        aliases=aliases,
    )


@pytest.fixture
def policy() -> ManagedGroupPolicy:
    return ManagedGroupPolicy(prefix="sg-", domain=MANAGED_DOMAIN)


@pytest.mark.unit
def test_canonical_email_prefers_managed_alias_over_primary_email(policy):
    """A managed-prefix alias in the managed domain wins over the primary email."""
    group = make_group("team@example.com", aliases=("sg-aws-admins@example.com",))

    assert policy.canonical_email(group) == "sg-aws-admins@example.com"


@pytest.mark.unit
def test_canonical_email_ignores_prefixed_alias_in_foreign_domain(policy):
    """A prefixed alias outside the managed domain must not be preferred."""
    group = make_group("team@example.com", aliases=("sg-aws-admins@other.test",))

    assert policy.canonical_email(group) == "team@example.com"


@pytest.mark.unit
def test_canonical_email_ignores_in_domain_alias_without_managed_prefix(policy):
    """An in-domain alias lacking the managed prefix must not be preferred."""
    group = make_group("team@example.com", aliases=("all-staff@example.com",))

    assert policy.canonical_email(group) == "team@example.com"


@pytest.mark.unit
def test_canonical_email_falls_back_to_primary_when_alias_tuple_empty(policy):
    """An empty alias tuple is legitimate, never an error."""
    group = make_group("sg-aws-admins@example.com")

    assert policy.canonical_email(group) == "sg-aws-admins@example.com"


@pytest.mark.unit
def test_canonical_email_takes_first_matching_alias_in_provider_order(policy):
    """Provider-reported alias order is the tie-break between two matches."""
    group = make_group(
        "team@example.com",
        aliases=("sg-aws-admins@example.com", "sg-aws-readers@example.com"),
    )

    assert policy.canonical_email(group) == "sg-aws-admins@example.com"


@pytest.mark.unit
def test_canonical_slug_returns_local_part_of_canonical_email(policy):
    """The slug comes from the canonical email, not from group_email."""
    group = make_group("team@example.com", aliases=("sg-aws-admins@example.com",))

    assert policy.canonical_slug(group) == "sg-aws-admins"


@pytest.mark.unit
def test_is_managed_is_false_for_group_outside_managed_domain(policy):
    """Feature boundary: an out-of-domain canonical email is not managed."""
    group = make_group("sg-aws-admins@other.test")

    assert policy.is_managed(group) is False


@pytest.mark.unit
def test_is_managed_is_true_when_managed_alias_rescues_foreign_primary(policy):
    """is_managed runs on the canonical value, not the primary email."""
    group = make_group("team@other.test", aliases=("sg-aws-admins@example.com",))

    assert policy.is_managed(group) is True


@pytest.mark.unit
def test_matches_prefix_matches_on_primary_email(policy):
    group = make_group("sg-aws-admins@example.com")

    assert policy.matches_prefix(group, "sg-aws-") is True


@pytest.mark.unit
def test_matches_prefix_matches_on_alias_when_primary_does_not(policy):
    group = make_group("team@example.com", aliases=("sg-aws-admins@example.com",))

    assert policy.matches_prefix(group, "sg-aws-") is True


@pytest.mark.unit
def test_matches_prefix_is_false_when_no_candidate_matches(policy):
    group = make_group("team@example.com", aliases=("all-staff@example.com",))

    assert policy.matches_prefix(group, "sg-aws-") is False


@pytest.mark.unit
def test_group_key_composes_slug_with_managed_domain(policy):
    assert policy.group_key("sg-aws-admins") == "sg-aws-admins@example.com"


@pytest.mark.unit
def test_group_key_normalizes_a_value_that_already_has_a_domain(policy):
    assert policy.group_key("  SG-AWS-Admins@Example.com ") == "sg-aws-admins@example.com"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("prefix", "domain"),
    [
        ("sg-", ""),
        ("sg-", "   "),
        ("", MANAGED_DOMAIN),
        ("   ", MANAGED_DOMAIN),
    ],
)
def test_managed_group_policy_rejects_blank_prefix_or_domain(prefix, domain):
    """A blank prefix would make every alias look managed; a blank domain is unusable."""
    with pytest.raises(ValueError):
        ManagedGroupPolicy(prefix=prefix, domain=domain)


@pytest.mark.unit
def test_from_config_derives_org_wide_prefix_and_normalizes_domain():
    """Prefix is derived from existing naming fields; no new setting is introduced."""
    config = AccessRuntimeConfig(
        dir_prefix="sg",
        dir_domain="  Example.COM ",
        dir_separator="-",
        platforms={},
    )

    policy = ManagedGroupPolicy.from_config(config)

    assert policy.prefix == "sg-"
    assert policy.domain == "example.com"
