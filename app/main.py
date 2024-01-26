import os
import json
import logging
from functools import partial
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from commands import atip, aws, incident, secret, sre, role
from commands.helpers import incident_helper, webhook_helper
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
    bot.command(f"/{PREFIX}talent-role")(role.role_command)
    bot.view("role_view")(role.role_view_handler)
    bot.action("role_change_locale")(role.update_modal_locale)

    # Register ATIP commands
    bot.command(f"/{PREFIX}atip")(atip.atip_command)
    bot.command(f"/{PREFIX}aiprp")(atip.atip_command)
    bot.action("ati_search_width")(atip.atip_width_action)
    bot.view("atip_view")(atip.atip_view_handler)
    bot.action("atip_change_locale")(atip.update_modal_locale)

    # Register AWS commands
    bot.command(f"/{PREFIX}aws")(aws.aws_command)
    bot.view("aws_access_view")(aws.access_view_handler)
    bot.view("aws_health_view")(aws.health_view_handler)

    # Register incident events
    bot.command(f"/{PREFIX}incident")(incident.open_modal)
    bot.view("incident_view")(incident.submit)
    bot.action("handle_incident_action_buttons")(
        incident.handle_incident_action_buttons
    )
    bot.action("incident_change_locale")(incident.handle_change_locale_button)

    # Incident events
    bot.action("add_folder_metadata")(incident_helper.add_folder_metadata)
    bot.action("view_folder_metadata")(incident_helper.view_folder_metadata)
    bot.view("view_folder_metadata_modal")(incident_helper.list_folders)
    bot.view("add_metadata_view")(incident_helper.save_metadata)
    bot.action("delete_folder_metadata")(incident_helper.delete_folder_metadata)
    bot.action("archive_channel")(incident_helper.archive_channel_action)
    bot.view("view_save_incident_roles")(incident_helper.save_incident_roles)

    # Register Secret command
    bot.command(f"/{PREFIX}secret")(secret.secret_command)
    bot.action("secret_change_locale")(secret.handle_change_locale_button)
    bot.view("secret_view")(secret.secret_view_handler)

    # Register SRE events
    bot.command(f"/{PREFIX}sre")(sre.sre_command)

    # Webhooks events
    bot.view("create_webhooks_view")(webhook_helper.create_webhook)
    bot.action("toggle_webhook")(webhook_helper.toggle_webhook)
    bot.action("reveal_webhook")(webhook_helper.reveal_webhook)
    bot.action("next_page")(webhook_helper.next_page)

    SocketModeHandler(bot, APP_TOKEN).connect()

    # Run scheduled tasks if not in dev
    if PREFIX == "":
        scheduled_tasks.init(bot)
        stop_run_continuously = scheduled_tasks.run_continuously()
        server_app.add_event_handler("shutdown", lambda: stop_run_continuously.set())


def get_bot():
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN", None)
    if not bool(SLACK_TOKEN):
        return False
    return App(token=SLACK_TOKEN)


bot = get_bot()

if bot:
    server_app.add_middleware(bot_middleware.BotMiddleware, bot=bot)
    server_app.add_event_handler("startup", partial(main, bot))
