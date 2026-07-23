"""Shared access-domain naming helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessGroupNaming:
    """Compute canonical IDP group names for a platform.

    Args:
        dir_prefix: Organization-wide group prefix (for example, ``sg``).
        dir_separator: Group slug segment separator (for example, ``-``).
    """

    dir_prefix: str
    dir_separator: str = "-"

    def group_prefix(self, platform: str) -> str:
        """Return the group slug prefix for a platform.

        Example: ``sg-aws-``.
        """
        return f"{self.dir_prefix}{self.dir_separator}{platform}{self.dir_separator}"

    def authn_group_slug(self, platform: str, authn_token: str = "authn") -> str:  # noqa: S107 -- default group-slug token, not a credential
        """Return the authn lifecycle group slug for a platform.

        Example: ``sg-aws-authn``.
        """
        return f"{self.group_prefix(platform)}{authn_token}"
