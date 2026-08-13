"""Platform-agnostic incident-summary feature package.

Exposes the ``/sre incident summarize`` Slack subcommand and its i18n
resources via pluggy hookimpls. Registration is startup-driven and side
effect free at import time (only decorated hookimpls are defined here).
"""

from pathlib import Path

from infrastructure.i18n.resources import I18nResourceSpec
from infrastructure.plugins import hookimpl
from packages.incident_summary.platforms import slack
from packages.incident_summary.service import TranscriptMessage, summarize_transcript


@hookimpl
def register_slack_commands(provider):
    """Register the incident_summary Slack commands.

    Args:
        provider: Slack platform provider instance.
    """
    slack.register_commands(provider)


@hookimpl
def register_i18n_resources(registry):
    """Register incident_summary translation resource locations.

    Args:
        registry: I18nResourceRegistry for registering resource specifications.
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
