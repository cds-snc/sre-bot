"""Webhooks capability: inbound webhook deliveries turned into typed events for features.

Holds the package's hookimpls, register_requirements first. Registration is
startup-driven and side effect free at import time: only decorated hookimpls
are defined here (decisions/plugins.md).
"""

from capabilities.webhooks.schemas import SENDER_KINDS_NAME, SENDER_KINDS_OWNER, SenderKindFile, build_sender_kind
from capabilities.webhooks.settings import content_settings
from contracts.content import ContentKind, ContentKindRegistrar
from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement


@hookimpl
def register_requirements() -> list[Requirement]:
    """Declare each vendor or capability capabilities.webhooks cannot run without; none yet."""
    return []


@hookimpl
def register_content_kinds(registrar: ContentKindRegistrar) -> None:
    """Register the sender kinds, optional until the first kinds ship."""
    settings = content_settings()
    registrar.register(
        ContentKind(
            owner=SENDER_KINDS_OWNER,
            name=SENDER_KINDS_NAME,
            model=SenderKindFile,
            build=build_sender_kind,
            max_file_bytes=settings.max_kind_file_bytes,
            max_items=settings.max_kinds,
        )
    )
