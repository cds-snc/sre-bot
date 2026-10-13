"""Incident comms subdomain: public status updates, drafted by a responder with optional AI help.

Exposes the ``/sre incident status-update`` Slack subcommand, the
status-updates modal's listeners and the comms i18n resources via pluggy
hookimpls. Registration is startup-driven and side effect free at import time
(only decorated hookimpls are defined here).
"""

from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.plugins.namespace import hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from features.incident.comms.entrypoints import slack


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the ``status-update`` subcommand and the status-updates modal listeners.

    Args:
        registrar: Slack command registrar.
    """
    slack.register(registrar)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register the incident comms translation resource location.

    The ``locales`` directory holds the ``incident_status_update`` catalogue;
    the loader reads every ``<domain>.<locale>.yml`` file under it.

    Args:
        registry: Registrar for translation resource specifications.
    """
    locales_path = Path(__file__).parent / "locales"
    registry.register(
        I18nResourceSpec(
            owner="features.incident.comms",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="incident_comms",
        )
    )
