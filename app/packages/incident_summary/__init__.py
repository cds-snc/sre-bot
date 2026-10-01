"""Platform-agnostic incident-summary feature package.

Exposes the ``/sre incident summarize`` Slack subcommand and its i18n
resources via pluggy hookimpls. Registration is startup-driven and side
effect free at import time (only decorated hookimpls are defined here).
"""

from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from packages.incident_summary.platforms import slack
from packages.incident_summary.service import TranscriptMessage, summarize_transcript


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the incident_summary Slack commands.

    Args:
        registrar: Slack command registrar.
    """
    slack.register_commands(registrar)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register incident_summary translation resource locations.

    Args:
        registry: Registrar for translation resource specifications.
    """
    locales_path = Path(__file__).parent / "locales"
    registry.register(
        I18nResourceSpec(
            owner="packages.incident_summary",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="incident_summary",
        )
    )


__all__ = [
    "TranscriptMessage",
    "summarize_transcript",
]
