import os
import logging
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from commands import incident, sre
from commands.helpers import incident_helper, webhook_helper
from server import bot_middleware, server

server_app = server.handler

logging.basicConfig(level=logging.INFO)

load_dotenv()


def main():
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    APP_TOKEN = os.environ.get("APP_TOKEN")

    PREFIX = os.environ.get("PREFIX", "")
    bot = App(token=SLACK_TOKEN)

    # Add bot to server_app
    server_app.add_middleware(bot_middleware.BotMiddleware, bot=bot)

    # Register incident events
    bot.command(f"/{PREFIX}incident")(incident.open_modal)
    bot.view("incident_view")(incident.submit)
    bot.action("handle_incident_action_buttons")(
        incident.handle_incident_action_buttons
    )

    # Incident events
    bot.action("add_folder_metadata")(incident_helper.add_folder_metadata)
    bot.action("view_folder_metadata")(incident_helper.view_folder_metadata)
    bot.view("view_folder_metadata_modal")(incident_helper.list_folders)
    bot.view("add_metadata_view")(incident_helper.save_metadata)
    bot.action("delete_folder_metadata")(incident_helper.delete_folder_metadata)

    # Register SRE events
    bot.command(f"/{PREFIX}sre")(sre.sre_command)

    # Webhooks events
    bot.view("create_webhooks_view")(webhook_helper.create_webhook)
    bot.action("toggle_webhook")(webhook_helper.toggle_webhook)
    bot.action("reveal_webhook")(webhook_helper.reveal_webhook)

    SocketModeHandler(bot, APP_TOKEN).connect()


server_app.add_event_handler("startup", main)
