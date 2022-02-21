from commands import incident
import os

from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()


def main():
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    APP_TOKEN = os.environ.get("APP_TOKEN")

    app = App(token=SLACK_TOKEN)

    # Register incident events
    app.command("/incident")(incident.open_modal)
    app.view("incident_view")(incident.submit)

    SocketModeHandler(app, APP_TOKEN).start()


if __name__ == "__main__":
    main()
