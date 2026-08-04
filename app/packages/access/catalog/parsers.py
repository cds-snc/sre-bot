"""Access Catalog entitlement token parsers.

Defines the ``CatalogSlugParser`` Protocol and platform-specific implementations.

Each parser decomposes a raw entitlement token (the segment after the platform
prefix is stripped) into structured fields: product, env, role, service, resource.

Parser registration is done in ``providers.py`` — the only place the parser map
is assembled.  Adding a parser for a new platform is a ``providers.py``-only change.
"""

from dataclasses import dataclass, field
from typing import Protocol

from packages.access.catalog.domain import ParsedEntitlementToken


class CatalogSlugParser(Protocol):
    """Contract for entitlement token parsers."""

    def parse(self, token: str) -> ParsedEntitlementToken:
        """Decompose a raw entitlement token into structured fields.

        Args:
            token: The entitlement token string (e.g. ``"platform-prod-admin"``).
                   The platform prefix has already been stripped by the caller.

        Returns:
            ``ParsedEntitlementToken``.  ``parsed=False`` when the token does
            not conform to the expected pattern.
        """
        ...


@dataclass
class AwsCatalogSlugParser:
    """Parses AWS entitlement tokens using the Product(-Env)?-Role(-Service)?(-Resource)? convention.

    Disambiguation relies on ``known_envs``: if a segment matches a known
    environment value, it is classified as ``env``; everything before it is
    ``product``; everything after follows Role(-Service)?(-Resource)?.

    When no segment matches a known env the token is parsed as
    Product-Role(-Service)?(-Resource)?.

    Args:
        known_envs: Case-insensitive set of environment qualifiers
                    (e.g. {"dev", "staging", "prod"}).
    """

    known_envs: set[str] = field(default_factory=set)

    def parse(self, token: str) -> ParsedEntitlementToken:
        """Parse an AWS entitlement token into structured fields."""
        segments = token.strip().lower().split("-")
        if len(segments) < 2:
            return ParsedEntitlementToken(raw=token, parsed=False)

        normalized_envs = {e.lower() for e in self.known_envs}
        env_index: int | None = None
        for i, seg in enumerate(segments):
            if seg in normalized_envs:
                env_index = i
                break

        if env_index is not None and env_index >= 1:
            product = "-".join(segments[:env_index])
            env: str | None = segments[env_index]
            remainder = segments[env_index + 1 :]
        else:
            # No env segment found; first segment is product, rest is role+
            product = segments[0]
            env = None
            remainder = segments[1:]

        if not remainder:
            return ParsedEntitlementToken(raw=token, parsed=False)

        role = remainder[0]
        service: str | None = remainder[1] if len(remainder) > 1 else None
        resource: str | None = remainder[2] if len(remainder) > 2 else None

        return ParsedEntitlementToken(
            raw=token,
            product=product,
            env=env,
            role=role,
            service=service,
            resource=resource,
            parsed=True,
        )


class FallbackCatalogSlugParser:
    """Default parser for platforms without a specific implementation.

    Always returns ``parsed=False`` with only ``raw`` populated.
    """

    def parse(self, token: str) -> ParsedEntitlementToken:
        """Return unparsed token entry."""
        return ParsedEntitlementToken(raw=token, parsed=False)
