import os
from . import aws_dev, google, slack

PREFIX = os.environ.get("PREFIX", "")


def dev_command(ack, logger, respond, client, body, args):
    ack()

    if PREFIX != "dev-":
        respond("This command is only available in the development environment.")
        return
    action = args.pop(0) if args else ""
    logger.info("Dev command received: %s", action)
    match action:
        case "aws":
            aws_dev.aws_dev_command(ack, client, body, respond, logger)
        case "google":
            google.google_service_command(ack, client, body, respond, logger)
        case "slack":
            slack.slack_command(ack, client, body, respond, logger, args)
        case "stale":
            test_stale_channel_notification(ack, logger, respond, client, body)


def test_stale_channel_notification(ack, logger, respond, client, body):
    ack()
    text = """👋  Hi! There have been no updates in this incident channel for 14 days! Consider scheduling a retro or archiving it.\n
        Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Pensez à planifier une rétro ou à l'archiver."""
    attachments = [
        {
            "text": "Would you like to archive the channel now or schedule a retro? | Souhaitez-vous archiver le canal maintenant ou planifier une rétro?",
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
    client.chat_postMessage(
        channel=body["channel_id"], text=text, attachments=attachments
    )
