from commands import utils
import logging

logging.basicConfig(level=logging.INFO)


def notify_stale_incident_channels(client):
    logging.info("Checking for stale incident channels")
    channels = utils.get_stale_channels(client)
    text = "👋  Hi! There have been no updates in this incident channel for 14 days! Consider archiving it."
    attachments = [
        {
            "text": "Would you like to archive the channel now?",
            "fallback": "You are unable to archive the channel",
            "callback_id": "archive_channel",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "archive",
                    "text": "Yes",
                    "type": "button",
                    "value": "archive",
                    "style": "danger",
                },
                {
                    "name": "ignore",
                    "text": "No",
                    "type": "button",
                    "value": "ignore",
                },
            ],
        }
    ]
    for channel in channels:
        client.chat_postMessage(channel=channel, text=text, attachments=attachments)
