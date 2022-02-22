from commands import utils


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
