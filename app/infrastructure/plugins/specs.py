"""Hook specifications for feature plugin lifecycle.

Covers the full lifecycle of a feature package:
  - Slack event listener registration (commands, views, actions, etc.)
  - HTTP route registration
  - Startup settings validation / cache warmup
"""

import pluggy
from fastapi import FastAPI
from slack_bolt.async_app import AsyncApp
from structlog.stdlib import BoundLogger

from infrastructure.events import EventDispatcher
from infrastructure.i18n import I18nResourceRegistry
from integrations.slack.provider import SlackPlatformProvider
from jobs import BackgroundJobRegistry

hookspec = pluggy.HookspecMarker("sre_bot")


class FeatureLifecycleSpecs:
    """Collection of hookspecs covering the full lifecycle of a feature plugin.

    This includes:
        - Startup validation and warmup
        - Slack listeners registration (passes the Bolt app for direct registration)
        - HTTP route registration
        - Background job registration
        - i18n resource registration
        - Event handler registration

    Each hookspec is optional and called at the appropriate point in the
    application lifecycle. Implement the ones relevant to your feature.
    """

    @hookspec
    def register_slack_commands(self, provider: "SlackPlatformProvider") -> None:
        """Register Slack commands with the provider.
        (DEPRECATED: will be removed in favor of register_slack_listeners for direct Bolt app registration)

        Args:
            provider: SlackPlatformProvider instance to register commands with.
        """

    @hookspec
    def register_slack_listeners(self, app: "AsyncApp") -> None:
        """Register Slack listeners directly on the Bolt app instance.
        Args:
            app: The Bolt AsyncApp instance to register listeners on.
        """

    @hookspec
    def register_routes(self, app: "FastAPI") -> None:
        """Register HTTP routes with the FastAPI application.

        Args:
            app: The FastAPI application instance.
        """

    @hookspec
    def register_i18n_resources(self, registry: "I18nResourceRegistry") -> None:
        """Register feature translation resource locations.

        Args:
            registry: I18nResourceRegistry for registering resource specifications.
        """

    @hookspec
    def register_event_handlers(self, dispatcher: "EventDispatcher") -> None:
        """Register feature event handlers with the application dispatcher.

        Args:
            dispatcher: The application-scoped event dispatcher.
        """

    @hookspec
    def register_background_jobs(self, registry: "BackgroundJobRegistry") -> None:
        """Register recurring feature jobs through the scheduler boundary.

        Args:
            registry: Scheduler-agnostic registry adapter used to register jobs.
        """

    @hookspec
    def startup_warmup(self, logger: "BoundLogger") -> None:
        """Validate feature settings and pre-warm caches at startup.

        Args:
            logger: Structured logger for recording initialization events.
        """
