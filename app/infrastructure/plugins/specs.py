"""Hook specifications for feature plugin lifecycle.

Covers the full lifecycle of a feature package:
  - Slack command registration
  - HTTP route registration
  - Startup settings validation / cache warmup
"""

import pluggy
from fastapi import FastAPI
from structlog.stdlib import BoundLogger

from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.events import EventDispatcher
from infrastructure.i18n import I18nResourceRegistry

hookspec = pluggy.HookspecMarker("sre_bot")


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
    def register_i18n_resources(self, registry: I18nResourceRegistry) -> None:
        """Register feature translation resource locations.

        Args:
            registry: I18nResourceRegistry for registering resource specifications.
        """

    @hookspec
    def register_event_handlers(self, dispatcher: EventDispatcher) -> None:
        """Register feature event handlers with the application dispatcher.

        Args:
            dispatcher: The application-scoped event dispatcher.
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
