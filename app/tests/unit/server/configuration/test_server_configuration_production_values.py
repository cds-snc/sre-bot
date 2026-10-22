"""Checked-in values of the host, Slack transport and Notify API-key-leak tables for each environment."""

import tomllib

import pytest

from server.configuration import CONFIG_DIR

pytestmark = pytest.mark.unit


def _table(environment: str, name: str) -> dict:
    with (CONFIG_DIR / f"{environment}.toml").open("rb") as file:
        return tomllib.load(file).get(name, {})


def test_production_server_table() -> None:
    """Production names its public address and the startup-message test channel."""
    table = _table("production", "server")

    assert table["public_base_url"] == "https://sre-bot.cdssandbox.xyz"
    assert table["sre_test_channel_id"] == "C033L7RGCT0"


def test_production_notify_api_key_leak_table() -> None:
    """Production posts API-key leaks to the Notify ops channel and mentions the on-call group."""
    table = _table("production", "notify_api_key_leak")

    assert table["channel_id"] == "CNWA63606"
    assert table["oncall_group_id"] == "S0BNW0G8CFK"


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_non_production_notify_api_key_leak_posts_to_the_test_channel(environment: str) -> None:
    """Local and ci post to the SRE test channel and mention no group."""
    table = _table(environment, "notify_api_key_leak")

    assert table["channel_id"] == "C033L7RGCT0"
    assert table["oncall_group_id"] == ""


def test_command_prefix_per_environment() -> None:
    """Production keeps commands unprefixed through the base file; local uses dev-."""
    assert _table("base", "slack_transport")["command_prefix"] == ""
    assert "slack_transport" not in _table("production", "slack_transport") or _table("production", "slack_transport") == {}
    assert _table("local", "slack_transport")["command_prefix"] == "dev-"


@pytest.mark.parametrize("name", ["server", "slack_transport", "notify_api_key_leak"])
def test_base_file_holds_each_table(name: str) -> None:
    """The base file carries every slice's table."""
    assert _table("base", name)
