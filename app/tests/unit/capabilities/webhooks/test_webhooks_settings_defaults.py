"""Unit tests for the [webhooks] slice: its table, its defaults and an override from a file.

Each test reads the slice through the files the package conftest installs, so it sees only
the values it writes.
"""

import tomllib
from pathlib import Path

import pytest

from capabilities.webhooks.settings import WebhooksSettings, content_settings, get_webhooks_settings
from contracts.configuration import ConfigurationError, ConfigurationSlice
from tests.unit.capabilities.webhooks.conftest import install_webhooks_files

pytestmark = pytest.mark.unit


def test_the_slice_reads_the_webhooks_table() -> None:
    config = WebhooksSettings.model_config

    assert issubclass(WebhooksSettings, ConfigurationSlice)
    assert (config.get("toml_table_header"), config.get("env_prefix")) == (("webhooks",), "WEBHOOKS__")


def test_the_limits_default_to_the_recorded_values() -> None:
    """The defaults are the content limits decisions/webhooks.md records."""
    limits = get_webhooks_settings().limits()

    assert (limits.max_conditions, limits.max_condition_depth, limits.max_extracted_fields) == (50, 2, 30)
    assert (limits.max_field_value_chars, limits.max_template_chars, limits.max_title_chars) == (4096, 2048, 150)
    assert (limits.max_loop_iterations, limits.max_kinds_per_instance, limits.email_lookups_per_message) == (100, 20, 10)
    assert (limits.max_list_items, limits.max_url_chars) == (50, 2048)
    assert (get_webhooks_settings().max_kinds, get_webhooks_settings().max_kind_file_bytes) == (200, 16384)


def test_an_environment_file_overrides_a_limit(tmp_path: Path) -> None:
    install_webhooks_files(tmp_path, environment="[webhooks]\nemail_lookups_per_message = 3\n")

    assert get_webhooks_settings().limits().email_lookups_per_message == 3


def test_a_limit_below_one_is_refused(tmp_path: Path) -> None:
    install_webhooks_files(tmp_path, environment="[webhooks]\nmax_conditions = 0\n")

    with pytest.raises(ConfigurationError):
        WebhooksSettings()


def test_content_is_checked_against_the_loaded_slice(tmp_path: Path) -> None:
    install_webhooks_files(tmp_path, environment="[webhooks]\nmax_conditions = 5\n")

    assert content_settings().max_conditions == 5


def test_content_is_checked_against_the_defaults_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The content validator runs over any root with no environment configuration installed."""
    monkeypatch.setattr("contracts.configuration._files", None)

    assert content_settings().limits() == WebhooksSettings.model_construct().limits()
    assert content_settings().max_conditions == 50


def test_a_post_attempt_fits_inside_the_inline_deadline() -> None:
    """Each platform call gets its own short timeout, so a post and the lookups fit one delivery."""
    assert get_webhooks_settings().post_attempt_timeout_seconds == 2


def test_the_ingest_bounds_default_to_the_recorded_values() -> None:
    """decisions/webhooks.md 3 Pipeline: a 5 s inline deadline, a 7-day inbox, SNS capped at twice its message."""
    settings = get_webhooks_settings()

    assert (settings.inline_processing_deadline_seconds, settings.inbox_ttl_seconds) == (5.0, 604800)
    assert (settings.aws_sns_max_body_bytes, settings.legacy_slack_json_max_body_bytes) == (524288, 262144)
    assert settings.aws_sns_content_types == ("text/plain", "application/json")
    assert (settings.sns_max_message_age_seconds, settings.max_json_depth) == (86400, 64)
    assert (settings.retry_base_seconds, settings.retry_max_seconds, settings.retry_max_attempts) == (30, 3600, 8)
    assert (settings.inbox_table_name, settings.instances_table_name) == ("sre_bot_webhook_inbox", "webhooks")


@pytest.mark.parametrize(
    "table",
    [
        pytest.param("inbox_ttl_seconds = 3600\nsns_max_message_age_seconds = 7200\n", id="replay-bound-past-the-dedupe-window"),
        pytest.param("retry_base_seconds = 600\nretry_max_seconds = 60\n", id="base-past-the-ceiling"),
        pytest.param("inline_processing_deadline_seconds = 60\n", id="deadline-past-the-sender-timeouts"),
    ],
)
def test_bounds_that_contradict_each_other_are_refused(tmp_path: Path, table: str) -> None:
    install_webhooks_files(tmp_path, environment=f"[webhooks]\n{table}")

    with pytest.raises(ConfigurationError):
        WebhooksSettings()


def test_the_base_file_sets_every_ingest_key_to_its_default() -> None:
    """app/config/base.toml carries each new key, so an organisation sees and tunes it in one place."""
    base = tomllib.loads((Path(__file__).parents[4] / "config" / "base.toml").read_text(encoding="utf-8"))["webhooks"]
    defaults = WebhooksSettings.model_construct()

    for key, value in base.items():
        expected = getattr(defaults, key)
        assert (tuple(value) if isinstance(value, list) else value) == expected, key
