from modules import sre

from unittest.mock import MagicMock, patch


def test_sre_command_calls_ack():
    ack = MagicMock()
    command = sre_command_helper("command")
    sre.sre_command(ack, command, MagicMock(), MagicMock(), MagicMock())
    ack.assert_called_once()


@patch("modules.sre.sre.logger")
def test_sre_command_calls_logger(
    logger_mock: MagicMock,
):
    command = sre_command_helper("command")
    sre.sre_command(MagicMock(), command, MagicMock(), MagicMock(), MagicMock())
    logger_mock.info.assert_called_once()


def test_sre_command_with_empty_string():
    respond = MagicMock()
    command = sre_command_helper("")
    sre.sre_command(MagicMock(), command, respond, MagicMock(), MagicMock())
    respond.assert_called_once_with(
        "Type `/sre help` to see a list of commands.\nTapez `/sre aide` pour voir une liste de commandes"
    )


@patch.object(sre, "GIT_SHA", "test_git_sha")
def test_sre_command_with_version_argument():
    respond = MagicMock()
    command = sre_command_helper("version")
    sre.sre_command(MagicMock(), command, respond, MagicMock(), MagicMock())
    respond.assert_called_once_with("SRE Bot version: test_git_sha")


def test_sre_command_with_help_argument():
    respond = MagicMock()
    command = sre_command_helper("help")
    sre.sre_command(MagicMock(), command, respond, MagicMock(), MagicMock())
    respond.assert_called_once_with(sre.help_text)


def test_sre_command_with_geolocate_argument_and_no_ip():
    respond = MagicMock()
    command = sre_command_helper("geolocate")
    sre.sre_command(
        MagicMock(),
        command,
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
    command = sre_command_helper("geolocate 111.111.111.111")
    sre.sre_command(
        MagicMock(),
        command,
        respond,
        MagicMock(),
        MagicMock(),
    )
    geolocate_mock.assert_called_once_with(["111.111.111.111"], respond)


@patch("modules.sre.sre.logger")
@patch("modules.sre.sre.incident_helper.handle_incident_command")
def test_sre_command_with_incident_argument(command_runner, logger_mock):
    command_runner.return_value = "incident command help"
    clientMock = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    command = sre_command_helper("incident")
    sre.sre_command(
        ack,
        command,
        respond,
        clientMock,
        body,
    )
    command_runner.assert_called_once_with(
        [], clientMock, body, respond, ack, logger_mock
    )


@patch("modules.sre.webhook_helper.handle_webhook_command")
def test_sre_command_with_webhooks_argument(command_runner):
    command_runner.return_value = "webhooks command help"
    clientMock = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    command = sre_command_helper("webhooks")
    sre.sre_command(MagicMock(), command, respond, clientMock, body)
    command_runner.assert_called_once_with([], clientMock, body, respond)


@patch("modules.sre.sre.dev_core.dev_command")
def test_sre_command_with_test_argument(mock_dev_command):
    mock_dev_command.return_value = "dev command help"
    respond = MagicMock()
    command = sre_command_helper("test")
    sre.sre_command(MagicMock(), command, respond, MagicMock(), MagicMock())
    mock_dev_command.assert_called_once()


@patch("modules.sre.sre.reports")
def test_sre_command_with_reports_argument(mock_reports):
    # mock_reports.reports_command.return_value = "report command help"
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    command = sre_command_helper("reports")
    sre.sre_command(ack, command, respond, client, body)
    mock_reports.reports_command.assert_called_once()


def test_sre_command_with_unknown_argument():
    respond = MagicMock()
    command = sre_command_helper("unknown")
    sre.sre_command(MagicMock(), command, respond, MagicMock(), MagicMock())
    respond.assert_called_once_with(
        "Unknown command: `unknown`. Type `/sre help` to see a list of commands. \nCommande inconnue: `unknown`. Entrez `/sre help` pour une liste des commandes valides"
    )


def sre_command_helper(text):
    """Helper function to create a command dictionary for testing."""
    return {
        "text": text,
        "user_id": "U123456",
        "user_name": "test_user",
        "channel_id": "C123456",
        "channel_name": "test_channel",
    }
