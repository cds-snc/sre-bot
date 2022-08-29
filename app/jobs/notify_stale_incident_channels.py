from commands import utils
import logging

logging.basicConfig(level=logging.INFO)


def notify_stale_incident_channels(client):
    logging.info("Checking for stale incident channels")
    channels = utils.get_stale_channels(client)
    text = """👋  Hi! There have been no updates in this incident channel for 14 days! Consider archiving it.\n
        Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Vous pouvez considérer l'archiver."""
    attachments = [
        {
            "text": "Would you like to archive the channel now? | Voulez-vous archiver ce canal maintenant?",
            "fallback": "You are unable to archive the channel | Vous ne pouvez pas archiver ce canal",
            "callback_id": "archive_channel",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "archive",
                    "text": "Yes | Oui",
                    "type": "button",
                    "value": "archive",
                    "style": "danger",
                },
                {
                    "name": "ignore",
                    "text": "No | Non",
                    "type": "button",
                    "value": "ignore",
                },
            ],
        }
    ]
    for channel in channels:
        client.chat_postMessage(
            channel=channel["id"], text=text, attachments=attachments
        )
