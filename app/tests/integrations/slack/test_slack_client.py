import unittest
from unittest.mock import patch
from integrations.slack.client import SlackClientManager


class TestSlackClientManager(unittest.TestCase):
    @patch("integrations.slack.client.settings.slack.SLACK_TOKEN", "test-token")
    @patch("integrations.slack.client.WebClient")
    def test_get_client_creates_instance(self, mock_web_client):
        SlackClientManager._client = None  # pylint: disable=protected-access

        # Call get_client and verify a WebClient instance is created
        client = SlackClientManager.get_client()
        mock_web_client.assert_called_once_with(token="test-token")
        self.assertEqual(client, mock_web_client.return_value)

    @patch("integrations.slack.client.WebClient")
    def test_get_client_returns_existing_instance(self, mock_web_client):
        mock_client = mock_web_client.return_value
        SlackClientManager._client = mock_client  # pylint: disable=protected-access

        # Call get_client and verify the existing instance is returned
        client = SlackClientManager.get_client()
        mock_web_client.assert_not_called()
        self.assertEqual(client, mock_client)


if __name__ == "__main__":
    unittest.main()
