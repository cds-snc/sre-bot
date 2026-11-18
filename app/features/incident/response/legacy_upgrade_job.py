"""One run of the incident legacy upgrade job: one service scope, the core runner, the mode's apply flag.

Imported only by the plugin module, which registers it. The runner logs the one
report event per run; a failure propagates to the scheduler's error boundary,
which logs it once with the traceback (decisions/reliability.md).

The job body is sync and runs on the scheduler's thread, while the legacy roles
reader is an async port. Each run opens one ``asyncio.Runner`` at this edge and
runs every roles read on it, so a run has one event loop and one context and
the core runner stays sync (decisions/outbound-clients.md, Migration).
TODO(TASK-145.13): drop the runner with the legacy roles step.
"""

import asyncio

from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.workplace import ConfiguredSystems, TenantVerifier
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.api import build_legacy_upgrade
from features.incident.response import providers


def run_legacy_upgrade(scopes: ServiceScopeOpener, *, apply: bool) -> None:
    """Resolve the records, the configured systems and the tenant verifier in one scope and run the upgrade.

    Args:
        scopes: Opens the per-run service scope.
        apply: Write the upgraded items; a dry run only reports.
    """
    legacy = providers.legacy_roles_reader()
    with scopes.create_scope() as services, asyncio.Runner() as runner:
        upgrade = build_legacy_upgrade(
            services.get(RecordStore),
            services.get(ConfiguredSystems),
            services.get(TenantVerifier),
            get_incident_core_settings(),
            read_roles=lambda report: runner.run(legacy.read(report)),
        )
        upgrade.run(apply=apply)
