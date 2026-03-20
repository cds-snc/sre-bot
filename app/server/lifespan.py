from contextlib import asynccontextmanager
import sys
import threading
from typing import AsyncIterator, Optional, TYPE_CHECKING, cast

from fastapi import FastAPI
from slack_bolt import App
from structlog.stdlib import BoundLogger

from infrastructure.logging.setup import configure_logging
from infrastructure.services import (
    discover_and_init_features,
    get_directory_provider,
    get_platform_service,
    get_settings,
    get_translation_service,
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


def _initialize_directory_provider(
    app: FastAPI,
    settings: "Settings",
    logger: BoundLogger,
) -> None:
    """Build, warm up, and store the directory provider on app.state."""
    log = logger.bind(phase="directory")
    log.info("directory_provider_initialization_started")

    directory_provider = get_directory_provider()

    if settings.directory.require_startup_warmup:
        warmup = directory_provider.warmup()
        if not warmup.is_success:
            log.error("directory_provider_initialization_failed", error=warmup.message)
            raise RuntimeError(f"directory_warmup_failed: {warmup.message}")
    else:
        log.info("directory_provider_warmup_skipped")

    app.state.directory_provider = directory_provider
    log.info("directory_provider_initialization_completed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger = _get_logger(settings)

    app.state.settings = settings
    app.state.logger = logger

    logger.info("application_startup")
    _list_configs(settings, logger)

    _initialize_directory_provider(app, settings, logger)

    app.state.command_providers = {}

    platform_service = get_platform_service()
    platform_providers = platform_service.load_providers()
    app.state.platform_service = platform_service
    app.state.platform_providers = platform_providers

    # Inject translator into platform providers for i18n support
    translation_service = get_translation_service()
    for provider in platform_providers.values():
        provider.set_translator(translation_service._translator)
    logger.info(
        "translation_service_injected_into_providers",
        provider_count=len(platform_providers),
    )

    discover_and_init_features(
        app=app,
        logger=logger,
        slack_provider=platform_providers.get("slack"),
        teams_provider=platform_providers.get("teams"),
        discord_provider=platform_providers.get("discord"),
    )
    logger.info(
        "feature_plugins_initialized",
        count=len(platform_providers),
        providers=list(platform_providers.keys()),
    )

    init_results = platform_service.initialize_all_providers()
    failed = [name for name, result in init_results.items() if not result.is_success]
    if failed:
        logger.warning(
            "platform_providers_initialization_partial_failure",
            failed=failed,
        )

    slack_provider = platform_providers.get("slack")
    if slack_provider and getattr(slack_provider, "app", None):
        slack_app = cast(App, slack_provider.app)
        _register_legacy_handlers(slack_app, logger)
        app.state.bot = slack_app
        app.state.socket_mode_handler = slack_provider.socket_mode_handler
        if not _is_test_environment():
            scheduled_stop_event = _start_scheduled_tasks(slack_app, settings, logger)
        else:
            scheduled_stop_event = None
    else:
        app.state.bot = None
        app.state.socket_mode_handler = None
        scheduled_stop_event = None

    if not _is_test_environment():
        start_results = platform_service.start_all_providers()
        failed_start = [
            name for name, result in start_results.items() if not result.is_success
        ]
        if failed_start:
            logger.warning("platform_providers_start_failed", failed=failed_start)

    app.state.scheduled_stop_event = scheduled_stop_event

    yield

    logger.info("application_shutdown")

    _stop_scheduled_tasks(app.state.scheduled_stop_event)

    platform_service.stop_all_providers()
