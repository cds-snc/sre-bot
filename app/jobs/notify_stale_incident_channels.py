import logging
from integrations.sentinel import log_to_sentinel
from integrations.slack import channels as slack_channels
from modules.incident.incident_helper import INCIDENT_CHANNELS_PATTERN

logging.basicConfig(level=logging.INFO)


def notify_stale_incident_channels(client):
    logging.info("Checking for stale incident channels")
    channels = slack_channels.get_stale_channels(
        client, pattern=INCIDENT_CHANNELS_PATTERN
    )
    text = """👋  Hi! There have been no updates in this incident channel for 14 days! Consider scheduling a retro or archiving it.\n
        Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Pensez à planifier une rétro ou à l'archiver."""
    attachments = [
        {
            "text": "Would you like to archive the channel now or schedule a retro? | Souhaitez-vous archiver la chaîne maintenant ou programmer une rétro?", 
            "fallback": "You are unable to archive the channel | Vous ne pouvez pas archiver ce canal",
            "callback_id": "archive_channel",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "archive",
                    "text": "Archive channel | Canal d'archives",
                    "type": "button",
                    "value": "archive",
                    "style": "danger",
                },
                {
                    "name": "schedule_retro",
                    "text": "Schedule Retro | Calendrier rétro",
                    "type": "button",
                    "value": "schedule_retro",
                    "style": "primary",
                },
                {
                    "name": "ignore",
                    "text": "Ignore | Ignorer",
                    "type": "button",
                    "value": "ignore",
                },
            ],
        }
    ]
    for channel in channels:
        log_to_sentinel("sent_stale_channel_notification", {"channel": channel})
        client.chat_postMessage(
            #channel=channel["id"], text=text, attachments=attachments
            channel="C06TVP0V5AR", text=text, attachments=attachments
        )
