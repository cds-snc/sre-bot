from functools import partial

from infrastructure.services import get_settings
from infrastructure.logging.setup import configure_logging

from infrastructure.events import (
    discover_and_register_handlers,
    log_registered_handlers,
    register_infrastructure_handlers,
)
from infrastructure.services import get_platform_service
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
    load_providers,
    get_active_providers,
    get_primary_provider_name,
)
from infrastructure.services import discover_and_register_platforms
from infrastructure.i18n.factory import create_translator

from server import bot_middleware, server
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

settings = get_settings()
configure_logging(settings=settings)  # Explicit structlog configuration

server_app = server.handler
logger = configure_logging(settings=settings)


def main(bot):
    """Main function to start the application."""
    # Log startup output
    logger.info(
        "application_startup",
    )
    list_configs()

    APP_TOKEN = settings.slack.APP_TOKEN
    PREFIX = settings.PREFIX

    # Register Roles commands
    role.register(bot)

    # Register ATIP module
    atip.register(bot)

    # Register AWS commands
    aws.register(bot)

    # Register Secret command
    secret.register(bot)

    # Register SRE events
    sre.register(bot)

    # Webhooks events
    webhook_helper.register(bot)

    # Register incident events
    incident.register(bot)

    # Incident events
    incident_helper.register(bot)

    SocketModeHandler(bot, APP_TOKEN).connect()

    # Run scheduled tasks if not in dev
    if PREFIX == "":
        scheduled_tasks.init(bot)
        stop_run_continuously = scheduled_tasks.run_continuously()
        server_app.add_event_handler("shutdown", lambda: stop_run_continuously.set())


def _initialize_platform_system():
    """Initialize platform system (Slack, Teams, Discord providers)."""
    # Get platform service singleton from provider
    platform_service = get_platform_service()

    # Load and register platform providers
    platform_providers = platform_service.load_providers()

    # Store platform service for app-wide access
    server_app.state.platform_service = platform_service
    server_app.state.platform_providers = platform_providers

    # Initialize enabled providers (establishes connections)
    init_results = platform_service.initialize_all_providers()

    initialized = [name for name, result in init_results.items() if result.is_success]
    failed = [name for name, result in init_results.items() if not result.is_success]

    if initialized:
        logger.info(
            "platform_providers_initialized",
            count=len(initialized),
            providers=initialized,
        )

    if failed:
        logger.warning(
            "platform_providers_initialization_failed",
            count=len(failed),
            providers=failed,
        )


def _register_platform_commands():
    """Auto-discover and register platform commands using Pluggy."""
    # Get provider instances (may be None if not initialized/enabled)
    platform_service = server_app.state.platform_service

    # Initialize translator for i18n support in help/error messages

    translator = create_translator()
    logger.info("translator_created_for_platform_system")

    slack_provider = None
    try:
        slack_provider = platform_service.get_provider("slack")
        if slack_provider:
            slack_provider.set_translator(translator)
            logger.info("translator_set_on_slack_provider")
        else:
            logger.warning("slack_provider_not_available")
    except Exception as e:
        logger.warning("failed_to_get_slack_provider", error=str(e))

    teams_provider = None
    try:
        teams_provider = platform_service.get_provider("teams")
        if teams_provider:
            teams_provider.set_translator(translator)
            logger.info("translator_set_on_teams_provider")
    except Exception as e:
        logger.warning("failed_to_get_teams_provider", error=str(e))

    discord_provider = None
    try:
        discord_provider = platform_service.get_provider("discord")
        if discord_provider:
            discord_provider.set_translator(translator)
            logger.info("translator_set_on_discord_provider")
    except Exception as e:
        logger.warning("failed_to_get_discord_provider", error=str(e))

    # Auto-discover and register all platform commands via Pluggy
    discover_and_register_platforms(
        slack_provider=slack_provider,
        teams_provider=teams_provider,
        discord_provider=discord_provider,
    )

    logger.info("platform_commands_registered")


# Ensure providers are activated once per FastAPI process at startup.
def providers_startup():
    """Activate group and command providers at startup."""
    # Register infrastructure handlers (audit, etc.) before any events
    try:
        register_infrastructure_handlers()
    except Exception as e:
        logger.error(
            "infrastructure_handlers_registration_failed",
            error=str(e),
        )

    # Auto-discover and register event handlers before activating providers (non-blocking)
    try:
        discover_and_register_handlers(base_path="modules", package_root="modules")
        log_registered_handlers()
    except Exception as e:
        logger.error(
            "event_handlers_discovery_failed",
            error=str(e),
        )

    # ========== NEW: Platform System Initialization ==========
    # Initialize platform system (Slack, Teams, Discord providers)
    # This runs alongside legacy providers during transition period
    try:
        _initialize_platform_system()
        _register_platform_commands()
    except Exception as e:
        # Log error but don't fail startup - platform system is optional during transition
        logger.error(
            "platform_system_initialization_failed",
            error=str(e),
            message="Platform system failed to initialize - continuing with legacy providers",
        )
    # ========== END: Platform System Initialization ==========

    # LEGACY: Group providers (will be migrated to platform system)
    try:
        primary = load_providers()
        # store for app-wide access
        server_app.state.providers = get_active_providers()
        server_app.state.primary_provider_name = get_primary_provider_name()
        logger.info(
            "group_providers_activated",
            primary=primary,
            total=len(server_app.state.providers),
        )
    except Exception as e:
        # Fail fast on provider activation error
        logger.error("group_providers_activation_failed", error=str(e))
        raise


def get_bot():
    SLACK_TOKEN = settings.slack.SLACK_TOKEN
    if not bool(SLACK_TOKEN):
        return False
    return App(token=SLACK_TOKEN)


def list_configs():
    """List all configuration settings keys"""
    config_settings = {"settings": []}

    for key, value in settings.model_dump().items():
        if isinstance(value, dict):
            config_settings[key] = list(value.keys())
        else:
            config_settings["settings"].append({key: value})

    logger.info("configuration_initialized", base_settings=config_settings["settings"])
    for key, value in config_settings.items():
        if key != "settings":
            logger.info("configuration_loaded", config_setting=key, keys=value)


def platform_shutdown():
    """Clean up platform provider connections on shutdown."""
    try:
        if hasattr(server_app.state, "platform_service"):
            platform_service = server_app.state.platform_service

            # Get all registered providers
            if hasattr(server_app.state, "platform_providers"):
                for provider_name in server_app.state.platform_providers.keys():
                    try:
                        provider = platform_service.get_provider(provider_name)
                        if hasattr(provider, "shutdown"):
                            provider.shutdown()
                        logger.info(
                            "platform_provider_shutdown",
                            provider=provider_name,
                        )
                    except Exception as e:
                        logger.error(
                            "platform_provider_shutdown_failed",
                            provider=provider_name,
                            error=str(e),
                        )

            logger.info("platform_system_shutdown_complete")
    except Exception as e:
        logger.error(
            "platform_shutdown_error",
            error=str(e),
        )


bot = get_bot()

if bot:
    server_app.add_middleware(bot_middleware.BotMiddleware, bot=bot)
    # register providers activation first so any handlers registered in main()
    # can rely on active providers.
    server_app.add_event_handler("startup", providers_startup)
    server_app.add_event_handler("startup", partial(main, bot))
    server_app.add_event_handler("shutdown", platform_shutdown)
else:
    # Even when Slack is not present, activate providers for FastAPI-first usage
    server_app.add_event_handler("startup", providers_startup)
    server_app.add_event_handler("shutdown", platform_shutdown)
