from integrations.slack import commands as slack_commands


def test_parse_command_empty_string():
    assert slack_commands.parse_command("") == []


def test_parse_command_no_args():
    assert slack_commands.parse_command("sre") == ["sre"]


def test_parse_command_one_arg():
    assert slack_commands.parse_command("sre foo") == ["sre", "foo"]


def test_parse_command_two_args():
    assert slack_commands.parse_command("sre foo bar") == ["sre", "foo", "bar"]


def test_parse_command_with_quotes():
    assert slack_commands.parse_command('sre "foo bar baz"') == ["sre", "foo bar baz"]


def test_parse_flags_no_flags():
    args, flags = slack_commands.parse_flags(["sre", "foo", "bar"])
    assert args == ["sre", "foo", "bar"]
    assert flags == {}


def test_parse_flags_with_flags():
    args, flags = slack_commands.parse_flags(
        ["sre", "foo", "--flag", "--key", "value", "-f"]
    )
    assert args == ["sre", "foo"]
    assert flags == {"flag": True, "key": "value", "f": True}
