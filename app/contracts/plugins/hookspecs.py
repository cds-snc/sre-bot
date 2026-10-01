"""Hook specifications for feature plugin lifecycle.

Covers the full lifecycle of a feature package:
  - Slack command registration
  - HTTP route registration
  - Startup settings validation / cache warmup
"""

from collections.abc import Callable
from typing import Any, Protocol

from fastapi import FastAPI
from structlog.stdlib import BoundLogger

from contracts.i18n.resources import I18nResourceRegistrar
from contracts.plugins.namespace import hookspec
from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.slack.registrar import SlackCommandRegistrar


class EventHandlerRegistrar(Protocol):
    """Registration boundary for feature event handlers.

    This protocol defines the exact contract feature packages must interact with.
    """

    def register_handler(self, event_type: str, handler: Callable[[Any], object]) -> None:
        """Register a handler for an event type."""
        ...


class FeatureLifecycleSpecs:
    """Collection of hookspecs covering the full lifecycle of a feature plugin.

    This includes:
        - Startup validation and warmup
        - Slack command registration (through the registrar Protocol)
        - HTTP route registration
        - Background job registration
        - i18n resource registration
        - Event handler registration

    Each hookspec is optional and called at the appropriate point in the
    application lifecycle. Implement the ones relevant to your feature.
    """

    @hookspec
    def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
        """Register Slack commands through the registrar.

        Args:
            registrar: Registrar to attach command handlers to; handlers reply
                through ``registrar.reply``.
        """

    @hookspec
    def register_routes(self, app: FastAPI) -> None:
        """Register HTTP routes with the FastAPI application.

        Args:
            app: The FastAPI application instance.
        """

    @hookspec
    def register_i18n_resources(self, registry: I18nResourceRegistrar) -> None:
        """Register feature translation resource locations.

        Args:
            registry: Registrar for translation resource specifications.
        """

    @hookspec
    def register_event_handlers(self, dispatcher: EventHandlerRegistrar) -> None:
        """Register feature event handlers with the application dispatcher.

        Args:
            dispatcher: Registrar for event handlers (the application-scoped event dispatcher).
        """

    @hookspec
    def register_background_jobs(self, registry: BackgroundJobRegistry) -> None:
        """Register recurring feature jobs through the scheduler boundary.

        Args:
            registry: Scheduler-agnostic registry adapter used to register jobs.
        """

    @hookspec
    def startup_warmup(self, logger: BoundLogger) -> None:
        """Validate feature settings and pre-warm caches at startup.

        Args:
            logger: Structured logger for recording initialization events.
        """
