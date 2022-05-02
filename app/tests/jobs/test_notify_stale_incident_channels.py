from jobs import notify_stale_incident_channels

from unittest.mock import MagicMock, patch


@patch("commands.utils.get_stale_channels")
def test_notify_stale_incident_channels(get_stale_channels_mock):
    get_stale_channels_mock.return_value = [{"id": "channel_id"}]
    client = MagicMock()
    notify_stale_incident_channels.notify_stale_incident_channels(client)
    client.chat_postMessage.assert_called_once_with(
        channel="channel_id",
        text="👋  Hi! There have been no updates in this incident channel for 14 days! Consider archiving it.",
        attachments=[
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
        ],
    )
