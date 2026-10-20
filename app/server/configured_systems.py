"""Host implementation of the configured-systems read over the vendor settings slices.

Host code, not infrastructure: which workplace systems an instance works with
is a workplace concern (``decisions/workplace-systems.md`` rule 3,
``decisions/plugin-architecture.md``). Each vendor has one tenant source in
TENANT_SOURCES that returns its tenant id, or None when the vendor is not
configured; a new system adds a row, not a parameter. The sources read each
validated slice's tenant entry: boot validation already rejects a blank Slack
id, and a Google entry missing its key or holding a blank id or the
my_customer alias.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import structlog

from contracts.workplace import WorkplaceSystem
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.slack.settings import SlackSettings, get_slack_settings

logger = structlog.get_logger(__name__)


class StaticConfiguredSystems:
    """Configured systems fixed at construction; the mapping is copied and read-only."""

    def __init__(self, tenants: Mapping[WorkplaceSystem, str]) -> None:
        self._tenants = MappingProxyType(dict(tenants))

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        """Return the tenant id of each configured system."""
        return self._tenants


@dataclass(frozen=True)
class TenantSource:
    """One workplace system and how to read its tenant id; read returns None when it is not configured."""

    system: WorkplaceSystem
    read: Callable[[], str | None]


def slack_tenant(settings: SlackSettings) -> str | None:
    """Return the Slack entry's tenant id, whether or not the transport is switched on."""
    tenant = settings.tenant
    return tenant.tenant_id if tenant is not None else None


def google_tenant(settings: GoogleWorkspaceSettings) -> str | None:
    """Return the Google entry's customer id."""
    tenant = settings.tenant
    return tenant.customer_id if tenant is not None else None


TENANT_SOURCES: tuple[TenantSource, ...] = (
    TenantSource(WorkplaceSystem.SLACK, lambda: slack_tenant(get_slack_settings())),
    TenantSource(WorkplaceSystem.GOOGLE, lambda: google_tenant(get_google_workspace_settings())),
)


def read_configured_systems(sources: Iterable[TenantSource] = TENANT_SOURCES) -> StaticConfiguredSystems:
    """Build the configured systems from the tenant sources, in source order."""
    tenants = {source.system: tenant for source in sources if (tenant := source.read()) is not None}
    logger.info("configured_systems_built", systems=[system.value for system in tenants])
    return StaticConfiguredSystems(tenants)
