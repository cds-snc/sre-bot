"""Tests for the Slack tenant entries in the checked-in configuration files.

Each environment's files are read with the real loader and the Slack slice is
built on them, with every SLACK__ secret blanked or set as the deployment sets
it. The recorded workspace id is the production sre-bot-config value, which is
also the development bot's workspace (auth.test): a change to either is a
deliberate edit of this test. The raw files are searched for token prefixes,
since a secret must never sit in a checked-in file.
"""

from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from integrations.slack.settings import SlackSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

RECORDED_TEAM_ID = "T2G2S06PM"


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slice from the files and the variables each test sets, never a developer's .env."""
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    for field in ("bot_token", "user_token", "app_token", "signing_secret"):
        monkeypatch.setenv(f"SLACK__{field.upper()}", "")
    yield


@pytest.mark.parametrize("environment", ["production", "local"])
def test_configuration_files_tenant_is_the_recorded_workspace(environment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Production and every development environment work in the recorded workspace."""
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-files-test")
    install_configuration_files(load_configuration_files(environment))

    tenant = SlackSettings().tenant

    assert tenant is not None
    assert tenant.team_id == RECORDED_TEAM_ID


def test_configuration_files_ci_has_no_tenant() -> None:
    """The test run configures no Slack workspace."""
    install_configuration_files(load_configuration_files("ci"))

    assert SlackSettings().tenant is None


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_configuration_files_hold_no_slack_token(name: str) -> None:
    """No checked-in file carries a Slack token or the signing secret."""
    text = (CONFIG_DIR / name).read_text(encoding="utf-8")

    for marker in ("xoxb-", "xoxp-", "xapp-", "bot_token", "user_token", "app_token", "signing_secret"):
        assert marker not in text
