"""Unit tests for webhook_helper module.

Tests cover:
- Webhook command parsing and dispatching
- List, create, and help functionality
- Error handling for unknown commands
"""

from unittest.mock import patch, MagicMock
from modules.sre import webhook_helper


class TestWebhookHelperActions:
    """Tests for webhook action acknowledgement."""

    def test_ack_action_calls_ack_function(self, mock_respond):
        """Should acknowledge Slack action immediately."""
        ack = MagicMock()
        webhook_helper.ack_action(ack)
        ack.assert_called_once()


class TestWebhookHelperCommands:
    """Tests for webhook command handling."""

    @patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
    @patch("modules.sre.webhook_helper.webhooks.lookup_webhooks")
    def test_handle_webhooks_with_empty_args_and_webhooks_found(
        self, mock_lookup, mock_list_view, mock_client, mock_body
    ):
        """Should display webhooks list when webhooks exist."""
        hooks = [
            {"id": "1", "name": "hook1", "channel": "channel_id"},
            {"id": "2", "name": "hook2", "channel": "channel_id"},
        ]
        mock_lookup.return_value = hooks
        respond = MagicMock()

        webhook_helper.handle_webhook_command([], mock_client, mock_body, respond)

        mock_list_view.assert_called_once_with(
            mock_client,
            mock_body,
            0,
            webhook_helper.MAX_BLOCK_SIZE,
            "all",
            hooks,
            channel=mock_body["channel_id"],
        )
        respond.assert_not_called()

    @patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
    @patch("modules.sre.webhook_helper.webhooks.lookup_webhooks")
    def test_handle_webhooks_with_empty_args_no_webhooks(
        self, mock_lookup, mock_list_view, mock_client, mock_body
    ):
        """Should show message when no webhooks exist."""
        mock_lookup.return_value = []
        respond = MagicMock()

        webhook_helper.handle_webhook_command([], mock_client, mock_body, respond)

        respond.assert_called_once_with(
            "No webhooks found for this channel. Type `/sre webhooks help` to see a list of commands."
        )
        mock_list_view.assert_not_called()

    @patch("modules.sre.webhook_helper.webhooks_create.create_webhook_modal")
    def test_handle_webhooks_create_command(
        self, mock_create_modal, mock_client, mock_body
    ):
        """Should open webhook creation modal."""
        webhook_helper.handle_webhook_command(
            ["create"],
            mock_client,
            mock_body,
            MagicMock(),
        )

        mock_create_modal.assert_called_once_with(mock_client, mock_body)

    def test_handle_webhooks_help_command(self, mock_client, mock_body):
        """Should display help text."""
        respond = MagicMock()
        webhook_helper.handle_webhook_command(["help"], mock_client, mock_body, respond)

        respond.assert_called_once_with(webhook_helper.help_text)

    @patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
    @patch("modules.sre.webhook_helper.webhooks.list_all_webhooks")
    def test_handle_webhooks_list_command(
        self, mock_list_all, mock_list_view, mock_client, mock_body
    ):
        """Should list all webhooks across channels."""
        all_hooks = [
            {"id": "1", "name": "hook1", "channel": "channel1"},
            {"id": "2", "name": "hook2", "channel": "channel2"},
        ]
        mock_list_all.return_value = all_hooks
        respond = MagicMock()

        webhook_helper.handle_webhook_command(["list"], mock_client, mock_body, respond)

        mock_list_view.assert_called_once_with(
            mock_client, mock_body, 0, webhook_helper.MAX_BLOCK_SIZE, "all", all_hooks
        )
        respond.assert_not_called()

    @patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
    @patch("modules.sre.webhook_helper.webhooks.list_all_webhooks")
    def test_handle_webhooks_list_command_no_webhooks(
        self, mock_list_all, mock_list_view, mock_client, mock_body
    ):
        """Should show message when no webhooks exist in list."""
        mock_list_all.return_value = []
        respond = MagicMock()

        webhook_helper.handle_webhook_command(["list"], mock_client, mock_body, respond)

        mock_list_view.assert_not_called()
        respond.assert_called_once_with("No webhooks found.")

    def test_handle_webhooks_unknown_command(self, mock_client, mock_body):
        """Should handle unknown commands gracefully."""
        respond = MagicMock()
        webhook_helper.handle_webhook_command(
            ["unknown"], mock_client, mock_body, respond
        )

        respond.assert_called_once_with(
            "Unknown command: `unknown`. Type `/sre webhooks help` to see a list of commands.\n"
            "Commande inconnue: `unknown`. Tapez `/sre webhooks help` pour voir une liste de commandes."
        )
