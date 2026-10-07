"""Incident scribe subdomain: AI-drafted incident documents and catch-up summaries.

Exposes the ``/sre incident draft`` and ``/sre incident summarize`` Slack
subcommands and their i18n resources via pluggy hookimpls. Registration is
startup-driven and side effect free at import time (only decorated hookimpls
are defined here).
"""

from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.plugins.namespace import hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.platforms import slack


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the incident scribe Slack commands.

    Args:
        registrar: Slack command registrar.
    """
    slack.register_commands(registrar)
    slack_entrypoints.register(registrar)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register the incident scribe translation resource location.

    The one ``locales`` directory holds both catalogues, ``incident_draft`` and
    ``incident_summary``. The registry keys resources on their path and the
    loader reads every ``<domain>.<locale>.yml`` file under it, so a single
    registration loads both.

    Args:
        registry: Registrar for translation resource specifications.
    """
    locales_path = Path(__file__).parent / "locales"
    registry.register(
        I18nResourceSpec(
            owner="packages.incident.scribe",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="incident_scribe",
        )
    )
