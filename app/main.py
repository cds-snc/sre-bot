import os
from functools import partial
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from modules import (
    secret,
    atip,
    aws,
    sre,
    webhook_helper,
    role,
    incident,
    incident_helper,
)
from core.config import settings
from core.logging import get_module_logger
from server import bot_middleware, server

from jobs import scheduled_tasks

server_app = server.handler
logger = get_module_logger()

load_dotenv()


def main(bot):
    """Main function to start the application."""
    # Log startup output
    logger.info(
        "application_startup",
    )
    list_configs()
    logger.info("environment_checked", config_keys=list(os.environ.keys()))

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


bot = get_bot()

if bot:
    server_app.add_middleware(bot_middleware.BotMiddleware, bot=bot)
    server_app.add_event_handler("startup", partial(main, bot))
