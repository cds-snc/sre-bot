from contextlib import asynccontextmanager
import sys
import threading
from typing import AsyncIterator, Optional, TYPE_CHECKING, cast

from fastapi import FastAPI
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from structlog.stdlib import BoundLogger

from infrastructure.commands.providers import load_providers as load_command_providers
from infrastructure.events import (
    discover_and_register_handlers,
    log_registered_handlers,
    register_infrastructure_handlers,
)
from infrastructure.logging.setup import configure_logging
from infrastructure.services import (
    # discover_and_register_platforms,
    # get_platform_service,
    get_settings,
)
from jobs import scheduled_tasks
from modules import (
    atip,
    aws,
    incident,
    incident_helper,
    role,
    secret,
    sre,
    webhook_helper,
)
from modules.groups.providers import (
    get_active_providers,
    get_primary_provider_name,
    load_providers,
)

if TYPE_CHECKING:
    from infrastructure.configuration import Settings


def _is_test_environment() -> bool:
    """Detect if running in a test environment."""
    return "pytest" in sys.modules


def _get_logger(settings: "Settings") -> BoundLogger:
    return configure_logging(settings=settings)


def _list_configs(settings: "Settings", logger: BoundLogger) -> None:
    config_settings: dict[str, list[object]] = {"settings": []}

    for key, value in settings.model_dump().items():
        if isinstance(value, dict):
            config_settings[key] = list(value.keys())
        else:
            config_settings["settings"].append({key: value})

    logger.info("configuration_initialized", base_settings=config_settings["settings"])
    for key, value in config_settings.items():
        if key != "settings":
            logger.info("configuration_loaded", config_setting=key, keys=value)


def _register_legacy_handlers(bot: App, logger: BoundLogger) -> None:
    logger.info("registering_legacy_handlers")
    role.register(bot)
    atip.register(bot)
    aws.register(bot)
    secret.register(bot)
    sre.register(bot)
    webhook_helper.register(bot)
    incident.register(bot)
    incident_helper.register(bot)


def _start_socket_mode(
    bot: App, app_token: str, logger: BoundLogger
) -> tuple[SocketModeHandler, threading.Thread]:
    handler = SocketModeHandler(bot, app_token)
    thread = threading.Thread(
        target=handler.connect,
        daemon=True,
        name="slack-socket-mode",
    )
    thread.start()
    logger.info("socket_mode_started")
    return handler, thread


def _start_scheduled_tasks(
    bot: App,
    settings: "Settings",
    logger: BoundLogger,
) -> Optional[threading.Event]:
    if settings.PREFIX != "":
        logger.info("scheduled_tasks_skipped", reason="prefix_not_empty")
        return None

    scheduled_tasks.init(bot)
    stop_event = cast(Optional[threading.Event], scheduled_tasks.run_continuously())
    logger.info("scheduled_tasks_started")
    return stop_event


def _stop_scheduled_tasks(stop_event: Optional[threading.Event]) -> None:
    if stop_event is None:
        return
    stop_event.set()


def _activate_providers(
    app: FastAPI,
    settings: "Settings",
    logger: BoundLogger,
) -> None:
    try:
        register_infrastructure_handlers()
    except Exception as exc:
        logger.error("infrastructure_handlers_registration_failed", error=str(exc))

    try:
        discover_and_register_handlers(base_path="modules", package_root="modules")
        log_registered_handlers()
    except Exception as exc:
        logger.error("event_handlers_discovery_failed", error=str(exc))

    try:
        primary = load_providers()
        app.state.providers = get_active_providers()
        app.state.primary_provider_name = get_primary_provider_name()
        logger.info(
            "group_providers_activated",
            primary=primary,
            total=len(app.state.providers),
        )
    except Exception as exc:
        logger.error("group_providers_activation_failed", error=str(exc))
        raise

    # TODO: Platform system providers integration - commented out pending redesign
    # This section was causing race conditions with Slack Socket Mode initialization.
    # Will be re-implemented after refactoring to reuse the legacy Slack App instance.
    # try:
    #     platform_service = get_platform_service()
    #     platform_providers = platform_service.load_providers()
    #     app.state.platform_service = platform_service
    #     app.state.platform_providers = platform_providers
    #
    #     # Discover and register platform commands for ALL enabled providers
    #     # The discover function handles None providers gracefully
    #     # This must happen BEFORE initialize_all_providers() to ensure handlers
    #     # are registered before Socket Mode starts consuming events
    #     discover_and_register_platforms(
    #         slack_provider=platform_providers.get("slack"),  # type: ignore
    #         teams_provider=platform_providers.get("teams"),  # type: ignore
    #         discord_provider=platform_providers.get("discord"),  # type: ignore
    #     )
    #
    #     logger.info(
    #         "platform_commands_registered",
    #         count=len(platform_providers),
    #         providers=list(platform_providers.keys()),
    #     )
    #
    #     # Initialize all enabled providers (establishes connections)
    #     # Done after handlers are registered to prevent race condition
    #     init_results = platform_service.initialize_all_providers()
    #     initialized = [
    #         name for name, result in init_results.items() if result.is_success
    #     ]
    #     failed = [
    #         name for name, result in init_results.items() if not result.is_success
    #     ]
    #
    #     if failed:
    #         logger.warning(
    #             "platform_providers_initialization_partial_failure",
    #             initialized=initialized,
    #             failed=failed,
    #         )
    #
    #     logger.info(
    #         "platform_providers_activated",
    #         count=len(platform_providers),
    #         providers=list(platform_providers.keys()),
    #         initialized=initialized,
    #     )
    # except Exception as exc:
    #     logger.error("platform_providers_activation_failed", error=str(exc))
    #     raise

    try:
        command_providers = load_command_providers(settings=settings)
        app.state.command_providers = command_providers

        if command_providers:
            logger.info(
                "command_providers_activated",
                count=len(command_providers),
                providers=list(command_providers.keys()),
            )
        else:
            logger.info(
                "api_only_mode",
                message="No command providers enabled - API endpoints only",
            )
    except Exception as exc:
        logger.error("command_providers_activation_failed", error=str(exc))
        raise


def _get_bot(settings: "Settings") -> Optional[App]:
    """Create Slack App instance if token available and not in test environment."""
    # Skip Slack initialization during tests
    if _is_test_environment():
        return None

    slack_token = settings.slack.SLACK_TOKEN
    if not bool(slack_token):
        return None

    return App(token=slack_token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger = _get_logger(settings)

    app.state.settings = settings
    app.state.logger = logger

    logger.info("application_startup")
    _list_configs(settings, logger)

    _activate_providers(app, settings, logger)

    bot = _get_bot(settings)
    app.state.bot = bot

    socket_mode_handler = None
    scheduled_stop_event = None

    if bot is not None:
        _register_legacy_handlers(bot, logger)
        socket_mode_handler, socket_mode_thread = _start_socket_mode(
            bot,
            settings.slack.APP_TOKEN,
            logger,
        )
        app.state.socket_mode_thread = socket_mode_thread
        scheduled_stop_event = _start_scheduled_tasks(bot, settings, logger)

    app.state.socket_mode_handler = socket_mode_handler
    app.state.scheduled_stop_event = scheduled_stop_event

    yield

    logger.info("application_shutdown")

    _stop_scheduled_tasks(app.state.scheduled_stop_event)

    if app.state.socket_mode_handler is not None:
        app.state.socket_mode_handler.close()
        logger.info("socket_mode_stopped")
