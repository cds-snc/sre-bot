import os

from modules import sre

from unittest.mock import MagicMock, patch


def test_sre_command_calls_ack():
    ack = MagicMock()
    sre.sre_command(
        ack, {"text": "command"}, MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    ack.assert_called_once()


def test_sre_command_calls_logger():
    logger = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "command"}, logger, MagicMock(), MagicMock(), MagicMock()
    )
    logger.info.assert_called_once()


def test_sre_command_with_empty_string():
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": ""}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    respond.assert_called_once_with(
        "Type `/sre help` to see a list of commands.\nTapez `/sre aide` pour voir une liste de commandes"
    )


def test_sre_command_with_version_argument():
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "version"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    respond.assert_called_once_with(
        f"SRE Bot version: {os.environ.get('GIT_SHA', 'unknown')}"
    )


def test_sre_command_with_help_argument():
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "help"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    respond.assert_called_once_with(sre.help_text)


def test_sre_command_with_geolocate_argument_and_no_ip():
    respond = MagicMock()
    sre.sre_command(
        MagicMock(),
        {"text": "geolocate"},
        MagicMock(),
        respond,
        MagicMock(),
        MagicMock(),
    )
    respond.assert_called_once_with(
        "Please provide an IP address.\nSVP fournir une adresse IP"
    )


@patch("modules.sre.sre.geolocate_helper.geolocate")
def test_sre_command_with_geolocate_argument_and_ip(geolocate_mock):
    respond = MagicMock()
    sre.sre_command(
        MagicMock(),
        {"text": "geolocate 111.111.111.111"},
        MagicMock(),
        respond,
        MagicMock(),
        MagicMock(),
    )
    geolocate_mock.assert_called_once_with(["111.111.111.111"], respond)


@patch("modules.sre.sre.incident_helper.handle_incident_command")
def test_sre_command_with_incident_argument(command_runner):
    command_runner.return_value = "incident command help"
    clientMock = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    logger = MagicMock()

    sre.sre_command(
        ack,
        {"text": "incident"},
        logger,
        respond,
        clientMock,
        body,
    )
    command_runner.assert_called_once_with([], clientMock, body, respond, ack, logger)


@patch("modules.sre.webhook_helper.handle_webhook_command")
def test_sre_command_with_webhooks_argument(command_runner):
    command_runner.return_value = "webhooks command help"
    clientMock = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "webhooks"}, MagicMock(), respond, clientMock, body
    )
    command_runner.assert_called_once_with([], clientMock, body, respond)


@patch("modules.dev.core.dev_command")
def test_sre_command_with_test_argument(mock_dev_command):
    mock_dev_command.return_value = "dev command help"
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "test"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    mock_dev_command.assert_called_once()


def test_sre_command_with_unknown_argument():
    respond = MagicMock()
    sre.sre_command(
        MagicMock(), {"text": "unknown"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    respond.assert_called_once_with(
        "Unknown command: `unknown`. Type `/sre help` to see a list of commands. \nCommande inconnue: `unknown`. Entrez `/sre help` pour une liste des commandes valides"
    )
