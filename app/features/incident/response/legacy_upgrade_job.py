"""One run of the incident legacy upgrade job: one service scope, the core runner, the mode's apply flag.

Imported only by the plugin module, which registers it. The runner logs the one
report event per run; a failure propagates to the scheduler's error boundary,
which logs it once with the traceback (decisions/reliability.md).
"""

from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.workplace import ConfiguredSystems, TenantVerifier
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.api import build_legacy_upgrade


def run_legacy_upgrade(scopes: ServiceScopeOpener, *, apply: bool) -> None:
    """Resolve the records, the configured systems and the tenant verifier in one scope and run the upgrade.

    Args:
        scopes: Opens the per-run service scope.
        apply: Write the upgraded items; a dry run only reports.
    """
    with scopes.create_scope() as services:
        upgrade = build_legacy_upgrade(
            services.get(RecordStore),
            services.get(ConfiguredSystems),
            services.get(TenantVerifier),
            get_incident_core_settings(),
        )
        upgrade.run(apply=apply)
