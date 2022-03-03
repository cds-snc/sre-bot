from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from commands import incident, sre

import logging
import os

logging.basicConfig(level=logging.INFO)


load_dotenv()


def main():
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    APP_TOKEN = os.environ.get("APP_TOKEN")

    PREFIX = os.environ.get("PREFIX", "")
    app = App(token=SLACK_TOKEN)

    # Register incident events
    app.command(f"/{PREFIX}incident")(incident.open_modal)
    app.view("incident_view")(incident.submit)

    # Register SRE events
    app.command(f"/{PREFIX}sre")(sre.sre_command)

    SocketModeHandler(app, APP_TOKEN).start()


if __name__ == "__main__":
    main()
