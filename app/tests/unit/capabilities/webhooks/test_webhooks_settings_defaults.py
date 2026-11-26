"""Unit tests for the [webhooks] slice: its table, its defaults and an override from a file.

Each test reads the slice through the files the package conftest installs, so it sees only
the values it writes.
"""

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
