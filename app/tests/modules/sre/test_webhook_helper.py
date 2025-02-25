from unittest.mock import MagicMock, patch
from modules import webhook_helper


def test_handle_webhooks_command_with_empty_args():
    respond = MagicMock()
    webhook_helper.handle_webhook_command([], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(webhook_helper.help_text)


@patch("modules.sre.webhook_helper.webhooks_create.create_webhook_modal")
def test_handle_webhooks_command_with_create_command(create_webhook_modal_mock):
    client = MagicMock()
    body = MagicMock()
    webhook_helper.handle_webhook_command(
        ["create"],
        client,
        body,
        MagicMock(),
    )

    create_webhook_modal_mock.assert_called_with(client, body)


def test_handle_webhooks_command_with_help():
    respond = MagicMock()
    webhook_helper.handle_webhook_command(["help"], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(webhook_helper.help_text)


@patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
def test_handle_webhooks_command_with_list_command(list_all_webhooks_mock):
    client = MagicMock()
    body = MagicMock()
    webhook_helper.handle_webhook_command(["list"], client, body, MagicMock())
    list_all_webhooks_mock.assert_called_with(
        client, body, 0, webhook_helper.MAX_BLOCK_SIZE, "all"
    )


def test_handle_webhooks_command_with_unkown_command():
    respond = MagicMock()
    webhook_helper.handle_webhook_command(
        ["unknown"], MagicMock(), MagicMock(), respond
    )
    respond.assert_called_once_with(
        "Unknown command: `unknown`. Type `/sre webhooks help` to see a list of commands.\nCommande inconnue: `unknown`. Tapez `/sre webhooks help` pour voir une liste de commandes."
    )
