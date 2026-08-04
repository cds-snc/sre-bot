"""Access Catalog internal domain models.

These dataclasses cross the boundary between the catalog service and the
HTTP transport layer.  They are never serialised directly — schemas.py
owns the HTTP-boundary Pydantic models.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ParsedEntitlementToken:
    """Structured breakdown of a platform entitlement token.

    ``raw`` is always populated.  All other fields are populated only when
    ``parsed=True``.  Callers must handle the ``parsed=False`` case: not all
    tokens conform to the expected naming convention.

    For AWS the convention is ``Product(-Env)?-Role(-Service)?(-Resource)?``
    and disambiguation relies on a configurable ``known_envs`` set.
    """

    raw: str
    product: str = ""
    env: str | None = None
    role: str = ""
    service: str | None = None
    resource: str | None = None
    parsed: bool = False


@dataclass(frozen=True)
class PlatformSummary:
    """High-level summary of one configured platform."""

    key: str
    display_name: str
    authn_group_slug: str
    entitlement_count: int | None = None


@dataclass(frozen=True)
class EntitlementEntry:
    """One discovered entitlement for a platform, with membership annotation."""

    token: str
    group_slug: str
    group_email: str
    mode: Literal["sync_managed", "ephemeral", "deactivated"]
    requestable: bool
    already_provisioned: bool | None
    parsed_token: ParsedEntitlementToken = field(default_factory=lambda: ParsedEntitlementToken(raw=""))
