import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Optional, cast

from fastapi import FastAPI
from pluggy import PluginManager
from slack_bolt import App
from structlog.stdlib import BoundLogger

from infrastructure.configuration import get_settings
from infrastructure.configuration.infrastructure.server import (
    ServerSettings,
    get_server_settings,
)
from infrastructure.directory import get_directory_provider
from infrastructure.i18n import (
    I18nResourceRegistry,
    I18nResourceSpec,
    TranslationService,
    get_translation_service,
)
from infrastructure.logging.setup import configure_logging
from infrastructure.platforms import get_platform_service
from infrastructure.plugins import (
    auto_discover_plugins,
    get_plugin_manager,
    register_feature_integrations,
)
from infrastructure.security import get_jwks_manager
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


def _initialize_security_services(
    app: FastAPI,
    settings: "ServerSettings",
    logger: BoundLogger,
) -> None:
    """Pre-initialize JWT/JWKS security infrastructure at startup.

    If ISSUER_CONFIG is not set the application starts in a degraded state:
    authenticated endpoints will return 500 at runtime.  A startup warning is
    logged so the misconfiguration is visible without blocking the process.
    """
    log = logger.bind(phase="security")
    log.info("security_services_initialization_started")
    issuer_config = settings.ISSUER_CONFIG
    if not issuer_config:
        log.warning(
            "security_services_no_issuer_config",
            detail="ISSUER_CONFIG not set; authenticated endpoints will fail at runtime",
        )
        return

    jwks_manager = get_jwks_manager()
    jwks_manager.warmup()
    log.info(
        "security_services_initialized",
        issuer_count=len(issuer_config),
    )


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


def _initialize_translation_service(
    pm: PluginManager, logger: BoundLogger
) -> TranslationService:
    """"""
    # Phase 1: Discover feature plugins and collect i18n resource registrations.
    log = logger.bind(phase="i18n_resource_collection")

    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    logger.info("feature_plugins_discovered", plugin_count=len(pm.get_plugins()))

    i18n_registry = I18nResourceRegistry()
    pm.hook.register_i18n_resources(registry=i18n_registry)
    logger.info(
        "i18n_resources_collected", resource_count=i18n_registry.get_resource_count()
    )

    # Phase 2: Initialize translation service with all registered resources.
    log = logger.bind(phase="i18n_initialization")
    translation_service = get_translation_service()
    i18n_resources = i18n_registry.list_specs()

    # Add default core locales path as required resource
    app_root = Path(__file__).resolve().parents[1]
    core_locales_path = app_root / "locales"
    if core_locales_path.exists():
        core_resource = I18nResourceSpec(
            owner="core",
            path=str(core_locales_path),
            required=True,
            format="yaml",
            domain="core",
        )
        all_resources = [core_resource] + i18n_resources
    else:
        all_resources = i18n_resources

    init_result = translation_service.initialize(resources=all_resources, strict=True)
    if not init_result.is_success:
        log.error("i18n_initialization_failed", error=init_result.message)
        raise RuntimeError(f"i18n initialization failed: {init_result.message}")

    health_result = translation_service.health_check()
    if not health_result.is_success:
        log.error("i18n_healthcheck_failed", error=health_result.message)
        raise RuntimeError(f"i18n health check failed: {health_result.message}")

    log.info("i18n_initialization_completed_and_healthy")
    return translation_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    server_settings = get_server_settings()
    logger = _get_logger(settings)

    app.state.settings = settings
    app.state.logger = logger

    logger.info("application_startup")
    _list_configs(settings, logger)

    _initialize_security_services(app, server_settings, logger)
    _initialize_directory_provider(app, settings, logger)

    app.state.command_providers = {}

    platform_service = get_platform_service()
    platform_providers = platform_service.load_providers()
    app.state.platform_service = platform_service
    app.state.platform_providers = platform_providers

    pm = get_plugin_manager()

    translation_service = _initialize_translation_service(pm, logger)
    # Inject translation service into all platform providers and their formatters
    # before command registration so help-text translations work at startup.
    platform_service.inject_translation_service(translation_service)

    # Phase 3: Register feature commands, routes, and run startup warmup.
    # Providers now have the translator set, so description_key translations
    # resolve correctly at registration time.
    log = logger.bind(phase="feature_registration")
    register_feature_integrations(
        app=app,
        logger=logger,
        slack_provider=platform_providers.get("slack"),
    )
    log.info("feature_integrations_registered")

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
