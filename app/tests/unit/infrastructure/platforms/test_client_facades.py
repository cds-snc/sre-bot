"""Tests for platform client facades (Slack)."""

from unittest.mock import Mock, patch
from infrastructure.platforms.clients import (
    SlackClientFacade,
)
from infrastructure.operations import OperationStatus


class TestSlackClientFacade:
    """Tests for SlackClientFacade."""

    def test_initialization(self):
        """Test Slack client facade initializes correctly."""
        client = SlackClientFacade(token="xoxb-test-token")
        assert client._client is not None
        assert client.raw_client is not None

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_post_message_success(self, mock_webclient_class):
        """Test posting a message successfully."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {
            "ok": True,
            "ts": "1234567890.123456",
            "data": {"ts": "1234567890.123456"},
        }
        mock_client.chat_postMessage.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d), data=mock_response
        )

        client = SlackClientFacade(token="xoxb-test")
        result = client.post_message(channel="C123", text="Hello")

        assert result.is_success
        assert result.data["ts"] == "1234567890.123456"
        mock_client.chat_postMessage.assert_called_once()

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_post_message_api_error(self, mock_webclient_class):
        """Test posting a message with API error response."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {"ok": False, "error": "channel_not_found"}
        mock_client.chat_postMessage.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d)
        )

        client = SlackClientFacade(token="xoxb-test")
        result = client.post_message(channel="C123", text="Hello")

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert "channel_not_found" in result.message

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_post_message_blocks(self, mock_webclient_class):
        """Test posting a message with Block Kit blocks."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {
            "ok": True,
            "ts": "1234567890.123456",
            "data": {"ts": "1234567890.123456"},
        }
        mock_client.chat_postMessage.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d), data=mock_response
        )

        client = SlackClientFacade(token="xoxb-test")
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
        result = client.post_message(channel="C123", blocks=blocks)

        assert result.is_success
        call_args = mock_client.chat_postMessage.call_args
        assert call_args.kwargs["blocks"] == blocks

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_update_message_success(self, mock_webclient_class):
        """Test updating a message successfully."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {"ok": True, "data": {"ts": "1234567890.123456"}}
        mock_client.chat_update.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d), data=mock_response
        )

        client = SlackClientFacade(token="xoxb-test")
        result = client.update_message(
            channel="C123", ts="1234567890.123456", text="Updated"
        )

        assert result.is_success
        mock_client.chat_update.assert_called_once()

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_list_conversations_success(self, mock_webclient_class):
        """Test listing conversations successfully."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {
            "ok": True,
            "channels": [{"id": "C123", "name": "general"}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_client.conversations_list.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d)
        )

        client = SlackClientFacade(token="xoxb-test")
        result = client.list_conversations()

        assert result.is_success
        assert len(result.data["channels"]) == 1
        assert result.data["channels"][0]["id"] == "C123"

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_get_user_info_success(self, mock_webclient_class):
        """Test getting user info successfully."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {"ok": True, "user": {"id": "U123", "name": "testuser"}}
        mock_client.users_info.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d)
        )

        client = SlackClientFacade(token="xoxb-test")
        result = client.get_user_info(user_id="U123")

        assert result.is_success
        assert result.data["id"] == "U123"

    @patch("infrastructure.platforms.clients.slack.WebClient")
    def test_open_view_success(self, mock_webclient_class):
        """Test opening a view (modal) successfully."""
        mock_client = Mock()
        mock_webclient_class.return_value = mock_client
        mock_response = {
            "ok": True,
            "view": {"id": "V123"},
            "data": {"view": {"id": "V123"}},
        }
        mock_client.views_open.return_value = Mock(
            get=lambda k, d=None: mock_response.get(k, d), data=mock_response["data"]
        )

        client = SlackClientFacade(token="xoxb-test")
        view = {"type": "modal", "title": {"type": "plain_text", "text": "Test"}}
        result = client.open_view(trigger_id="trigger123", view=view)

        assert result.is_success
        assert result.data["view"]["id"] == "V123"
