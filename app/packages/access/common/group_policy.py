"""Feature-side owner of managed-group policy.

The DirectoryProvider is deliberately generic and no longer decides which of a
group's addresses is canonical, nor whether a group is managed; this module is
where those decisions live for the access feature.
"""

from dataclasses import dataclass

from infrastructure.directory.models import DirectoryGroup
from packages.access.common.config.settings import AccessRuntimeConfig
from packages.access.common.naming import AccessGroupNaming


@dataclass(frozen=True)
class ManagedGroupPolicy:
    """Pure value object deciding managed-group identity for access.

    Args:
        prefix: Organization-wide managed-group prefix (for example, ``sg-``).
        domain: Authoritative email domain of managed groups.
    """

    prefix: str
    domain: str

    def __post_init__(self) -> None:
        """Normalize both fields and reject blanks.

        A blank prefix is not merely useless: every ``startswith`` check would
        succeed, making every alias look managed.
        """
        prefix = self.prefix.strip().lower()
        domain = self.domain.strip().lower()
        if not prefix:
            raise ValueError("managed_group_policy_invalid: prefix must be a non-empty value")
        if not domain:
            raise ValueError("managed_group_policy_invalid: domain must be a non-empty value")
        object.__setattr__(self, "prefix", prefix)
        object.__setattr__(self, "domain", domain)

    @classmethod
    def from_config(cls, config: AccessRuntimeConfig) -> ManagedGroupPolicy:
        """Build the policy from the access runtime configuration."""
        naming = AccessGroupNaming(
            dir_prefix=config.dir_prefix,
            dir_separator=config.dir_separator,
        )
        return cls(prefix=naming.managed_prefix, domain=config.dir_domain)

    def canonical_email(self, group: DirectoryGroup) -> str:
        """Return the group's canonical managed address.

        The first alias in provider-reported order whose local part carries the
        managed prefix and whose domain is the managed domain wins; otherwise
        the primary group email.
        """
        for alias in group.aliases:
            candidate = alias.strip().lower()
            local_part, _, domain = candidate.partition("@")
            if domain == self.domain and local_part.startswith(self.prefix):
                return candidate
        return group.group_email.strip().lower()

    def canonical_slug(self, group: DirectoryGroup) -> str:
        """Return the local part of the group's canonical email."""
        return self.canonical_email(group).partition("@")[0]

    def is_managed(self, group: DirectoryGroup) -> bool:
        """Return whether the group's canonical email sits in the managed domain."""
        return self.canonical_email(group).partition("@")[2] == self.domain

    def matches_prefix(self, group: DirectoryGroup, prefix: str) -> bool:
        """Return whether the primary email or any alias carries ``prefix``."""
        normalized = prefix.strip().lower()
        candidates = (group.group_email, *group.aliases)
        return any(candidate.strip().lower().startswith(normalized) for candidate in candidates)

    def group_key(self, slug: str) -> str:
        """Return the managed group address for a slug, never a bare slug."""
        value = slug.strip().lower()
        if "@" in value:
            return value
        return f"{value}@{self.domain}"
