import os

from commands import sre

from unittest.mock import MagicMock


def test_sre_command_calls_ack():
    ack = MagicMock()
    sre.sre_command(ack, {"text": "command"}, MagicMock(), MagicMock())
    ack.assert_called_once()


def test_sre_command_calls_logger():
    logger = MagicMock()
    sre.sre_command(MagicMock(), {"text": "command"}, logger, MagicMock())
    logger.info.assert_called_once()


def test_sre_command_with_empty_string():
    respond = MagicMock()
    sre.sre_command(MagicMock(), {"text": ""}, MagicMock(), respond)
    respond.assert_called_once_with("Type `/sre help` to see a list of commands.")


def test_sre_command_with_version_argument():
    respond = MagicMock()
    sre.sre_command(MagicMock(), {"text": "version"}, MagicMock(), respond)
    respond.assert_called_once_with(
        f"SRE Bot version: {os.environ.get('GIT_SHA', 'unknown')}"
    )


def test_sre_command_with_help_argument():
    respond = MagicMock()
    sre.sre_command(MagicMock(), {"text": "help"}, MagicMock(), respond)
    respond.assert_called_once_with(
        """
\n `/sre help` - show this help text
\n `/sre version` - show the version of the SRE Bot"""
    )


def test_sr_command_with_unknown_argument():
    respond = MagicMock()
    sre.sre_command(MagicMock(), {"text": "unknown"}, MagicMock(), respond)
    respond.assert_called_once_with(
        "Unknown command: unknown. Type `/sre help` to see a list of commands."
    )
