from jobs import notify_stale_incident_channels

from unittest.mock import MagicMock, patch


@patch("integrations.slack.channels.get_stale_channels")
@patch("jobs.notify_stale_incident_channels.log_to_sentinel")
def test_notify_stale_incident_channels(_log_to_sentinel_mock, get_stale_channels_mock):
    get_stale_channels_mock.return_value = [{"id": "channel_id"}]
    client = MagicMock()
    notify_stale_incident_channels.notify_stale_incident_channels(client)
    client.chat_postMessage.assert_called_once_with(
        channel="channel_id",
        text="👋  Hi! There have been no updates in this incident channel for 14 days! Consider archiving it.\n\n        Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Vous pouvez considérer l'archiver.",
        attachments=[
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
        ],
    )
