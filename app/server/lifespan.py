import sys
import threading
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import cast

import structlog
import svcs
from fastapi import FastAPI
from slack_bolt import App
from structlog.stdlib import BoundLogger

from contracts.configuration import HostInfo
from contracts.i18n.resources import I18nResourceSpec
from contracts.services import ServiceScopeOpener
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.directory import (
    DirectorySettings,
    get_directory_provider,
)
from infrastructure.i18n import (
    I18nResourceRegistry,
    TranslationService,
    get_translation_service,
)
from infrastructure.security import get_jwks_manager
from infrastructure.security.settings import SecuritySettings
from integrations.slack.provider import get_slack_provider
from jobs import scheduled_tasks
from jobs.settings import SchedulerSettings
from modules import (
    atip,
    aws,
    dev,
    incident,
    incident_helper,
    role,
    secret,
    sre,
    webhook_helper,
)
from server.configuration import HostConfiguration
from server.configuration.summary import summarize
from server.plugins.boot import call_hook_per_plugin, plugin_built_slices, reset_plugin_built_slices
from server.plugins.manager import (
    FeaturePluginManager,
    get_plugin_manager,
    load_plugins,
    register_background_jobs,
    register_feature_integrations,
    resolve_plugin_requirements,
)
from server.services import SvcsServiceScopeOpener, initialize_core_services


def _is_test_environment() -> bool:
    """Detect if running in a test environment."""
    return "pytest" in sys.modules


def _get_logger_from_app() -> BoundLogger:
    # The configuration phase in the app factory already configured logging.
    return structlog.stdlib.get_logger()


def _log_plugin_configuration_summary(logger: BoundLogger) -> None:
    """Log the slices each plugin's boot first built: a section per plugin, each with its own hash.

    A disabled plugin never builds its slices, so it has no section.
    """
    sections: list[dict[str, object]] = []
    for plugin, built in plugin_built_slices().items():
        summary = summarize(built)
        sections.append({"plugin": plugin, "config_hash": summary.config_hash, "slices": summary.sections()})
    logger.info("plugin_configuration_summary", phase="plugin_boot", plugins=sections)


def _register_legacy_handlers(bot: App, logger: BoundLogger) -> None:
    logger.info("registering_legacy_handlers")
    role.register(bot)
    atip.register(bot)
    aws.register(bot)
    secret.register(bot)
    webhook_helper.register(bot)
    incident.register(bot)
    incident_helper.register(bot)


def _register_legacy_slack_commands(registrar: SlackCommandRegistrar, logger: BoundLogger) -> None:
    sre.register_commands(registrar)
    dev.register_commands(registrar)
    logger.info("legacy_slack_commands_registered", modules=["sre", "dev"])


def _start_scheduled_tasks(
    scheduler: SchedulerSettings,
    logger: BoundLogger,
    service_scopes: ServiceScopeOpener,
) -> threading.Event | None:
    # [scheduler] enabled is the run switch; Tier-2 leases are the duplicate-prevention
    # mechanism across replicas.
    if not scheduler.enabled:
        logger.info("scheduled_tasks_skipped", reason="scheduler_disabled")
        return None

    scheduled_tasks.init(register_background_jobs, service_scopes)
    stop_event = cast(threading.Event | None, scheduled_tasks.run_continuously())
    logger.info("scheduled_tasks_started")
    return stop_event


def _stop_scheduled_tasks(stop_event: threading.Event | None) -> None:
    if stop_event is None:
        return
    stop_event.set()


def _initialize_security_services(
    settings: SecuritySettings,
    logger: BoundLogger,
) -> None:
    """Pre-initialize JWT/JWKS security infrastructure at startup.

    If [security] lists no issuers the application starts in a degraded state:
    authenticated endpoints will return 500 at runtime. The configuration phase
    already logged the security_setting_weakened warning, so the warmup is skipped.
    """
    log = logger.bind(phase="security")
    log.info("security_services_initialization_started")
    issuer_config = settings.issuer_config
    if not issuer_config:
        return

    jwks_manager = get_jwks_manager()
    jwks_manager.warmup()
    log.info(
        "security_services_initialized",
        issuer_count=len(issuer_config),
    )


def _initialize_directory_provider(
    app: FastAPI,
    directory_settings: DirectorySettings,
    logger: BoundLogger,
) -> None:
    """Build, warm up, and store the directory provider on app.state."""
    log = logger.bind(phase="directory")
    log.info("directory_provider_initialization_started")

    directory_provider = get_directory_provider()

    if directory_settings.require_startup_warmup:
        warmup = directory_provider.warmup()
        if not warmup.is_success:
            log.error("directory_provider_initialization_failed", error=warmup.message)
            raise RuntimeError(f"directory_warmup_failed: {warmup.message}")
    else:
        log.info("directory_provider_warmup_skipped")

    app.state.directory_provider = directory_provider
    log.info("directory_provider_initialization_completed")


def _initialize_translation_service(pm: FeaturePluginManager, logger: BoundLogger) -> TranslationService:
    """Collect the plugins' i18n resources, then initialize and health-check the translation service.

    Plugins must already be loaded so every feature's locale path is included.
    """
    i18n_registry = I18nResourceRegistry()
    call_hook_per_plugin(pm, "register_i18n_resources", logger, registry=i18n_registry)
    logger.bind(phase="i18n_resource_collection").info(
        "i18n_resources_collected", resource_count=i18n_registry.get_resource_count()
    )

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


def build_lifespan(configuration: HostConfiguration) -> Callable[[FastAPI], AbstractAsyncContextManager[dict[str, object]]]:
    """Return the app lifespan bound to the configuration the app factory loaded."""

    @svcs.fastapi.lifespan
    async def lifespan(app: FastAPI, registry: svcs.Registry) -> AsyncGenerator[None]:
        async with asynccontextmanager(_serve)(app, registry, configuration):
            yield

    return lifespan


async def _serve(app: FastAPI, registry: svcs.Registry, configuration: HostConfiguration) -> AsyncGenerator[None]:
    # Phase 1 (configuration) ran in the app factory: the files are installed and every host
    # slice is validated. This phase only reads what it loaded.
    host = configuration.host_info
    server_settings = configuration.server
    security_settings = configuration.security
    directory_settings = configuration.directory
    sre_ops_settings = configuration.sre_ops
    logger = _get_logger_from_app()

    app.state.host_info = host
    app.state.logger = logger
    registry.register_value(HostInfo, host)

    logger.info("application_startup")
    # Phase 2: build every core service once; a failing factory stops startup here.
    await initialize_core_services(registry, logger)
    service_scopes = SvcsServiceScopeOpener(registry)

    _initialize_security_services(security_settings, logger)
    _initialize_directory_provider(app, directory_settings, logger)

    slack_transport = configuration.slack_transport
    app.state.slack_provider = get_slack_provider(
        enabled=slack_transport.enabled,
        socket_mode=slack_transport.socket_mode,
        command_prefix=slack_transport.command_prefix,
    )

    pm = get_plugin_manager()
    reset_plugin_built_slices()
    # Any plugin that fails to load stops startup here, before the app serves.
    load_plugins(pm, configuration.disabled_plugins, logger.bind(phase="plugin_loading"))
    # An enabled plugin whose required vendor or capability is not configured stops startup here.
    resolve_plugin_requirements(pm, logger.bind(phase="plugin_requirements"))

    translation_service = _initialize_translation_service(pm, logger)
    # Inject translation service into all platform providers and their formatters
    # before command registration so help-text translations work at startup.
    app.state.slack_provider.set_translator(translation_service.translator)
    app.state.slack_provider.set_scope_opener(service_scopes)
    # Phase 3: Register feature commands, routes, and run startup warmup.
    # Providers now have the translator set, so description_key translations
    # resolve correctly at registration time.
    log = logger.bind(phase="feature_registration")
    register_feature_integrations(
        app=app,
        logger=logger,
        slack_provider=app.state.slack_provider,
    )
    log.info("feature_integrations_registered")
    _log_plugin_configuration_summary(logger)
    # Legacy sre and dev subcommands must be in the provider's registry before
    # initialize_app binds the root slash commands.
    _register_legacy_slack_commands(app.state.slack_provider, logger)

    app.state.slack_provider.initialize_app()
    if app.state.slack_provider and getattr(app.state.slack_provider, "app", None):
        logger.info("slack_provider_app_available")
        slack_app = cast(App, app.state.slack_provider.app)
        _register_legacy_handlers(slack_app, logger)
        app.state.bot = slack_app
        app.state.socket_mode_handler = app.state.slack_provider.socket_mode_handler
        if sre_ops_settings.SRE_OPS_CHANNEL_ID:
            app.state.bot.client.chat_postMessage(
                channel=sre_ops_settings.SRE_OPS_CHANNEL_ID,
                text="SRE Bot has started up and is ready to receive commands.",
            )
        if server_settings.sre_test_channel_id:
            app.state.bot.client.chat_postMessage(
                channel=server_settings.sre_test_channel_id,
                text="SRE Bot has started up in test mode.",
            )
    else:
        logger.warning("slack_provider_app_unavailable", reason="initialization_failed")
        app.state.bot = None
        app.state.socket_mode_handler = None

    if not _is_test_environment():
        start_slack_result = app.state.slack_provider.start()
        if not start_slack_result.is_success:
            logger.warning(
                "slack_provider_start_failed",
                error=start_slack_result.message,
            )
    else:
        logger.info("slack_provider_start_skipped", reason="test_environment")

    # Phase 6 starts the scheduler alongside the transports, never through one of them.
    app.state.scheduled_stop_event = _start_scheduled_tasks(configuration.scheduler, logger, service_scopes)

    yield

    logger.info("application_shutdown")

    _stop_scheduled_tasks(app.state.scheduled_stop_event)

    if app.state.slack_provider:
        app.state.slack_provider.stop()
