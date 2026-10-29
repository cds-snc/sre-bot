"""Tests for the Slack vendor slice on the [slack] table and its provider.

Each test writes a base file and an environment file into tmp_path and installs
them, so it observes only the values it writes and sets. Every SLACK__ variable
is removed first and the .env file is disabled unless a test passes its own.
Failures are read from the ConfigurationError message, which must name the key
and never carry a token: the rendered traceback is searched for each token value.
"""

import re
import traceback
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from integrations.slack.settings import SlackSettings, SlackTenant, get_slack_settings
from server.configuration.loader import TomlConfigurationFiles, load_configuration_files

pytestmark = pytest.mark.unit

BOT_TOKEN = "xoxb-secret-bot-0001"
USER_TOKEN = "xoxp-secret-user-0001"
APP_TOKEN = "xapp-secret-app-0001"
SIGNING_SECRET = "secret-signing-0001"

_SECRETS = {
    "SLACK__BOT_TOKEN": BOT_TOKEN,
    "SLACK__USER_TOKEN": USER_TOKEN,
    "SLACK__APP_TOKEN": APP_TOKEN,
    "SLACK__SIGNING_SECRET": SIGNING_SECRET,
}

_TENANT = '[slack.tenant]\nteam_id = "T0TENANT"\n'


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear the slice's variables, the .env file and the cached singleton."""
    for name in (*_SECRETS, "SLACK__TENANT__TEAM_ID", "SLACK__COMMAND_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    for field in SlackSettings.model_fields:
        monkeypatch.delenv(f"SLACK__{field.upper()}", raising=False)
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    get_slack_settings.cache_clear()
    yield
    get_slack_settings.cache_clear()


def _install(tmp_path: Path, base: str = "[slack]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def _rendered(error: BaseException) -> str:
    return "".join(traceback.format_exception(error))


def test_slack_settings_is_a_slice_on_the_slack_table() -> None:
    """The slice reads the [slack] table with the SLACK__ prefix and rejects unknown keys."""
    config = SlackSettings.model_config

    assert issubclass(SlackSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("slack",)
    assert config.get("env_prefix") == "SLACK__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(SlackSettings.model_fields))
def test_slack_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its SLACK__<FIELD> name or file key: no alias widens it."""
    info = SlackSettings.model_fields[field]

    assert info.alias is None
    assert info.validation_alias is None


def test_slack_settings_reads_non_secret_values_from_the_slack_table(tmp_path: Path) -> None:
    """Timeouts, the retry budget and the error-code lists come from [slack], the environment file over the base."""
    _install(
        tmp_path,
        base='[slack]\nrequest_timeout_seconds = 25\nretry_max_attempts = 5\nnot_found_errors = ["base_missing"]\n',
        environment='[slack]\nretry_max_attempts = 7\ntransient_errors = ["env_transient"]\n',
    )

    settings = SlackSettings()

    assert settings.request_timeout_seconds == 25
    assert settings.retry_max_attempts == 7
    assert settings.not_found_errors == ["base_missing"]
    assert settings.transient_errors == ["env_transient"]


def test_slack_settings_defaults_equal_the_base_file() -> None:
    """The field defaults match the checked-in base.toml [slack] values, so neither drifts."""
    from_files = SlackSettings()
    defaults = {name: info.get_default(call_default_factory=True) for name, info in SlackSettings.model_fields.items()}

    assert from_files.model_dump() == defaults


def test_slack_settings_reads_the_tenant_from_the_tenant_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[slack.tenant] team_id builds the frozen tenant entry; the bot token comes from SLACK__BOT_TOKEN."""
    monkeypatch.setenv("SLACK__BOT_TOKEN", BOT_TOKEN)
    _install(tmp_path, environment=_TENANT)

    settings = SlackSettings()

    assert settings.tenant == SlackTenant(team_id="T0TENANT")
    assert settings.tenant.tenant_id == "T0TENANT"
    assert settings.bot_token.get_secret_value() == BOT_TOKEN


def test_slack_settings_reads_every_secret_from_its_slack_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tokens and the signing secret are read as SLACK__<FIELD> and stay out of the repr."""
    for name, value in _SECRETS.items():
        monkeypatch.setenv(name, value)
    _install(tmp_path, environment=_TENANT)

    settings = SlackSettings()

    assert (
        settings.bot_token.get_secret_value(),
        settings.user_token.get_secret_value(),
        settings.app_token.get_secret_value() if settings.app_token else None,
        settings.signing_secret.get_secret_value() if settings.signing_secret else None,
    ) == (
        BOT_TOKEN,
        USER_TOKEN,
        APP_TOKEN,
        SIGNING_SECRET,
    )
    for value in _SECRETS.values():
        assert value not in repr(settings)


def test_slack_settings_without_tenant_or_secrets_is_unconfigured(tmp_path: Path) -> None:
    """No tenant entry and no secret is an unconfigured Slack: it builds with empty credentials."""
    _install(tmp_path)

    settings = SlackSettings()

    assert settings.tenant is None
    assert settings.bot_token.get_secret_value() == ""
    assert settings.user_token.get_secret_value() == ""
    assert settings.app_token is None
    assert settings.signing_secret is None


def test_slack_settings_empty_secrets_count_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank SLACK__<FIELD> values, as the test run sets them, are absent and fail no rule."""
    for name in _SECRETS:
        monkeypatch.setenv(name, "")
    _install(tmp_path)

    settings = SlackSettings()

    assert settings.app_token is None
    assert settings.signing_secret is None


def test_slack_settings_tenant_without_the_bot_token_fails_naming_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tenant entry needs the bot token: every Slack call is made with it."""
    monkeypatch.setenv("SLACK__APP_TOKEN", APP_TOKEN)
    _install(tmp_path, environment=_TENANT)

    with pytest.raises(ConfigurationError, match="SLACK__BOT_TOKEN is required when \\[slack.tenant\\] is set") as raised:
        SlackSettings()

    assert APP_TOKEN not in _rendered(raised.value)


@pytest.mark.parametrize("name", list(_SECRETS))
def test_slack_settings_secret_without_the_tenant_fails_naming_the_key(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any Slack secret set without a tenant entry is a half-configured Slack and fails naming the secret."""
    monkeypatch.setenv(name, _SECRETS[name])
    _install(tmp_path)

    with pytest.raises(ConfigurationError, match=f"{name} is set but \\[slack.tenant\\] team_id is not") as raised:
        SlackSettings()

    assert _SECRETS[name] not in _rendered(raised.value)


@pytest.mark.parametrize(
    ("environment", "location"),
    [
        ("[slack]\nunknown_key = 1\n", "[slack] unknown_key"),
        ('[slack.tenant]\nteam_id = "T0TENANT"\nunknown_key = 1\n', "[slack] tenant.unknown_key"),
        ('[slack.tenant]\nteam_id = "   "\n', "[slack] tenant.team_id"),
    ],
)
def test_slack_settings_invalid_file_entry_fails_naming_file_table_and_key(
    environment: str, location: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown key in [slack] or [slack.tenant], or a blank team id, fails naming where to fix it."""
    monkeypatch.setenv("SLACK__BOT_TOKEN", BOT_TOKEN)
    _install(tmp_path, environment=environment)

    with pytest.raises(ConfigurationError, match=re.escape(location)) as raised:
        SlackSettings()

    assert str(tmp_path / "local.toml") in str(raised.value)


def test_slack_settings_strips_the_team_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Surrounding whitespace is not part of the opaque workspace id."""
    monkeypatch.setenv("SLACK__BOT_TOKEN", BOT_TOKEN)
    _install(tmp_path, environment='[slack.tenant]\nteam_id = " T0TENANT "\n')

    assert SlackSettings().tenant == SlackTenant(team_id="T0TENANT")


def test_slack_settings_tenant_entry_is_frozen() -> None:
    """The tenant entry is a value: it cannot be changed after the slice is built."""
    tenant = SlackTenant(team_id="T0TENANT")

    with pytest.raises(ValueError, match="frozen"):
        tenant.team_id = "T0OTHER"  # type: ignore[misc]


def test_slack_settings_command_prefix_does_not_fail_the_slice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SLACK__COMMAND_PREFIX, still set by the production task definition, is not a [slack] key and is ignored."""
    monkeypatch.setenv("SLACK__COMMAND_PREFIX", "dev-")
    dotenv = tmp_path / ".env"
    dotenv.write_text("SLACK__COMMAND_PREFIX=dev-\n", encoding="utf-8")
    _install(tmp_path)

    settings = SlackSettings(_env_file=dotenv)  # type: ignore[call-arg]

    assert settings.tenant is None
    assert "command_prefix" not in SlackSettings.model_fields


def test_slack_settings_local_shape_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The checked-in local.toml tenant with Codespaces-style SLACK__ tokens is a configured development Slack."""
    monkeypatch.setenv("SLACK__BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("SLACK__APP_TOKEN", APP_TOKEN)
    install_configuration_files(load_configuration_files("local"))

    settings = SlackSettings()

    assert settings.tenant is not None
    assert settings.app_token is not None
    assert settings.app_token.get_secret_value() == APP_TOKEN


def test_slack_settings_transport_switches_are_not_fields() -> None:
    """Whether and how the transport runs is the [slack_transport] slice's, not this one's."""
    assert "enabled" not in SlackSettings.model_fields
    assert "socket_mode" not in SlackSettings.model_fields


@pytest.mark.parametrize("field", ["INCIDENT_CHANNEL", "SLACK_SECURITY_USER_GROUP_ID", "SLACK_NOTIFY_MGMT_USER_GROUP_ID"])
def test_slack_settings_domain_fields_are_absent(field: str) -> None:
    """Feature ids (channels, user groups) live with the consuming feature."""
    assert field.lower() not in SlackSettings.model_fields


def test_get_slack_settings_is_a_singleton_until_cleared() -> None:
    """The provider caches one instance per process; clearing the cache builds a fresh one."""
    first = get_slack_settings()

    assert get_slack_settings() is first
    get_slack_settings.cache_clear()
    assert get_slack_settings() is not first
