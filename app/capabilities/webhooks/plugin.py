"""Webhooks capability: inbound webhook deliveries turned into typed events for features.

Holds the package's hookimpls, register_requirements first. Registration is
startup-driven and side effect free at import time: only decorated hookimpls
are defined here (decisions/plugins.md).
"""

from pathlib import Path

from capabilities.webhooks.hookspecs import WebhooksSpecs
from capabilities.webhooks.schemas import sender_kinds_content_kind
from capabilities.webhooks.service import WebhookExtensions, initialize_extensions
from contracts.content import ContentKindRegistrar
from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.plugins.extension_points import ExtensionPoint, ExtensionPointRegistrar
from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement


@hookimpl
def register_requirements() -> list[Requirement]:
    """Declare each vendor or capability capabilities.webhooks cannot run without; none yet."""
    return []


@hookimpl
def register_content_kinds(registrar: ContentKindRegistrar) -> None:
    """Register the sender kinds, optional until the first kinds ship."""
    registrar.register(sender_kinds_content_kind())


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register the capability's catalogue: the bot's own wording, such as the fallback header."""
    registry.register(
        I18nResourceSpec(
            owner="capabilities.webhooks",
            path=str(Path(__file__).parent / "locales"),
            required=False,
            format="yaml",
            domain="webhooks",
        )
    )


@hookimpl
def register_extension_points(registrar: ExtensionPointRegistrar) -> None:
    """Declare the event-consumer extension point; an empty point is valid (the poster serves)."""
    registrar.declare(ExtensionPoint(specs=WebhooksSpecs, provides=WebhookExtensions, initialize=initialize_extensions))
