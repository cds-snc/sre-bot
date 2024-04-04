import os
import json
import logging
from functools import partial
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from modules import (
    google_service,
    secret,
    atip,
    aws,
    sre,
    webhook_helper,
    role,
    incident,
    incident_helper,
)
from server import bot_middleware, server

from jobs import scheduled_tasks

server_app = server.handler

logging.basicConfig(level=logging.INFO)

load_dotenv()


def main(bot):
    # Log startup output
    logging.info(f"Starting up with SHA {os.environ.get('GIT_SHA', 'unknown')}")
    logging.info(f"ENV keys: {json.dumps(list(os.environ.keys()))}")

    APP_TOKEN = os.environ.get("APP_TOKEN")
    PREFIX = os.environ.get("PREFIX", "")

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

    # Register Google Service command for dev purposes only
    if PREFIX == "dev-":
        bot.command(f"/{PREFIX}google")(google_service.google_service_command)
        # bot.command(f"/{PREFIX}google")(google_service.google_schedule_command)
        bot.view("google_service_view")(google_service.open_modal)


def get_bot():
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN", None)
    if not bool(SLACK_TOKEN):
        return False
    return App(token=SLACK_TOKEN)


bot = get_bot()

if bot:
    server_app.add_middleware(bot_middleware.BotMiddleware, bot=bot)
    server_app.add_event_handler("startup", partial(main, bot))
