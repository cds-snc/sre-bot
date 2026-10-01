"""Platform-agnostic incident-document drafting feature package.

Exposes the ``/sre incident draft`` Slack subcommand and its i18n resources
via pluggy hookimpls. Registration is startup-driven and side effect free at
import time (only decorated hookimpls are defined here).
"""

from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from packages.incident_draft.domain import (
    DocumentSection,
    DraftedDocument,
    SectionDraft,
    TranscriptMessage,
)
from packages.incident_draft.platforms import slack
from packages.incident_draft.service import draft_incident_document


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the incident_draft Slack commands.

    Args:
        registrar: Slack command registrar.
    """
    slack.register_commands(registrar)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register incident_draft translation resource locations.

    Args:
        registry: Registrar for translation resource specifications.
    """
    locales_path = Path(__file__).parent / "locales"
    registry.register(
        I18nResourceSpec(
            owner="packages.incident_draft",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="incident_draft",
        )
    )


__all__ = [
    "DocumentSection",
    "DraftedDocument",
    "SectionDraft",
    "TranscriptMessage",
    "draft_incident_document",
]
