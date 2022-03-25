from commands import utils

from unittest.mock import MagicMock


def test_log_ops_message():
    client = MagicMock()
    msg = "foo bar baz"
    utils.log_ops_message(client, msg)
    client.chat_postMessage.assert_called_with(
        channel="C0388M21LKZ", text=msg, as_user=True
    )


def test_parse_command_empty_string():
    assert utils.parse_command("") == []


def test_parse_command_no_args():
    assert utils.parse_command("sre") == ["sre"]


def test_parse_command_one_arg():
    assert utils.parse_command("sre foo") == ["sre", "foo"]


def test_parse_command_two_args():
    assert utils.parse_command("sre foo bar") == ["sre", "foo", "bar"]


def test_parse_command_with_quotes():
    assert utils.parse_command('sre "foo bar baz"') == ["sre", "foo bar baz"]
