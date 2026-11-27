"""The incident.response plugin: its requirements, the new-incident policy check, its Slack commands and the incident legacy upgrade job.

The entry point names this module, not the package, because the host
configuration phase and the legacy modules read ``response/settings.py`` before
plugins load (decisions/plugins.md). Registration is startup-driven and side
effect free at import time (only decorated hookimpls are defined here).
TODO(TASK-145.13): delete the job's registration and its ``upgrade_*`` keys once a
production run reports nothing pending.
"""

from datetime import timedelta
from pathlib import Path

import structlog

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement
from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.workplace import ConfiguredSystems
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.api import resolve_new_incident_system
from features.incident.response.entrypoints import slack
from features.incident.response.legacy_upgrade_job import run_legacy_upgrade
from features.incident.response.settings import UpgradeMode, get_incident_response_settings

logger = structlog.get_logger()

UPGRADE_JOB_NAME = "incident_legacy_upgrade"


@hookimpl
def register_requirements() -> tuple[Requirement, ...]:
    """Require the Slack and Google Workspace tenants and the handbook id.

    The upgrade writes references in both systems; declare, the feature's core
    path, links every new incident to the handbook.
    """
    return (
        Requirement("slack.tenant"),
        Requirement("google_workspace.tenant"),
        Requirement("incident_response.handbook_id"),
    )


@hookimpl
def startup_warmup(logger: structlog.stdlib.BoundLogger, systems: ConfiguredSystems) -> None:
    """Resolve the new-incident policy, so a policy that names no usable system aborts boot naming the key.

    Raises:
        SettingError: The policy does not resolve against the configured systems.
    """
    system = resolve_new_incident_system(get_incident_core_settings().new_incident_system, systems)
    logger.debug("incident_new_incident_system_resolved", system=system.value)


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the incident commands under ``/sre incident`` and ``/incident`` with the declare form and alert buttons.

    Args:
        registrar: Slack command registrar.
    """
    slack.register(registrar)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register the incident response translation resource location.

    The ``locales`` directory holds the ``incident_response`` catalogue.

    Args:
        registry: Registrar for translation resource specifications.
    """
    registry.register(
        I18nResourceSpec(
            owner="features.incident.response",
            path=str(Path(__file__).parent / "locales"),
            required=False,
            format="yaml",
            domain="incident_response",
        )
    )


@hookimpl
def register_background_jobs(registry: BackgroundJobRegistry) -> None:
    """Register the incident legacy upgrade as a leased interval job unless its mode is off.

    Args:
        registry: Scheduler-agnostic registry; its scope opener serves each run.
    """
    settings = get_incident_response_settings()
    if settings.upgrade_mode is UpgradeMode.OFF:
        logger.debug("incident_legacy_upgrade_not_registered", reason="upgrade_mode_off")
        return

    scopes = registry.service_scopes
    apply = settings.upgrade_mode is UpgradeMode.APPLY

    def incident_legacy_upgrade() -> None:
        run_legacy_upgrade(scopes, apply=apply)

    registry.register_interval(
        job_name=UPGRADE_JOB_NAME,
        every=timedelta(minutes=settings.upgrade_interval_minutes),
        job=incident_legacy_upgrade,
        lease_ttl=timedelta(seconds=settings.upgrade_lease_ttl_seconds),
    )
