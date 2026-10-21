"""Integration tests for the configuration files in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed (core services, security,
directory, the Slack provider, plugins, translation), so only the
configuration phase does real work. The loader's directory is pointed at a
tmp_path holding base.toml and ci.toml (pytest-env sets ENVIRONMENT=ci), the
logging slice cache is cleared and its .env file disabled. A bad file must stop
startup before the lifespan yields and before core services are built; valid
files must be installed before the logging slice is built from them.
"""

from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from contracts.configuration import ConfigurationError, installed_configuration_files
from infrastructure.logging.settings import LoggingSettings, get_logging_settings
from server.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the loader at tmp_path and build the logging slice fresh for each test."""
    monkeypatch.setattr("server.configuration.loader.CONFIG_DIR", tmp_path)
    monkeypatch.setitem(LoggingSettings.model_config, "env_file", None)
    get_logging_settings.cache_clear()
    yield tmp_path
    get_logging_settings.cache_clear()


def _stub_later_phases(stack: ExitStack) -> AsyncMock:
    provider = MagicMock()
    provider.app = None
    core_services = AsyncMock()
    stack.enter_context(patch("server.lifespan.initialize_core_services", core_services))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.load_plugins"))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
    stack.enter_context(patch("server.lifespan._start_scheduled_tasks"))
    stack.enter_context(patch("server.lifespan._stop_scheduled_tasks"))
    return core_services


async def _boot_fails_naming(*parts: str) -> None:
    reached_yield = False
    with ExitStack() as stack:
        core_services = _stub_later_phases(stack)
        with pytest.raises(ConfigurationError) as raised:
            async with lifespan(FastAPI()):
                reached_yield = True

    assert reached_yield is False
    core_services.assert_not_awaited()
    for part in parts:
        assert part in str(raised.value)


async def test_unknown_logging_key_fails_boot_naming_file_table_and_key(_config_dir: Path) -> None:
    (_config_dir / "base.toml").write_text('[logging]\nlog_level = "INFO"\n', encoding="utf-8")
    (_config_dir / "ci.toml").write_text('[logging]\nlog_levle = "DEBUG"\n', encoding="utf-8")

    await _boot_fails_naming(str(_config_dir / "ci.toml"), "[logging]", "log_levle")


async def test_missing_environment_file_fails_boot_naming_it(_config_dir: Path) -> None:
    (_config_dir / "base.toml").write_text('[logging]\nlog_level = "INFO"\n', encoding="utf-8")

    await _boot_fails_naming(str(_config_dir / "ci.toml"))


async def test_valid_files_are_installed_before_the_logging_slice_is_built(_config_dir: Path) -> None:
    (_config_dir / "base.toml").write_text('[logging]\nlog_level = "INFO"\n', encoding="utf-8")
    (_config_dir / "ci.toml").write_text('[logging]\nlog_level = "WARNING"\n', encoding="utf-8")

    with ExitStack() as stack:
        _stub_later_phases(stack)
        async with lifespan(FastAPI()):
            assert installed_configuration_files().paths == (_config_dir / "base.toml", _config_dir / "ci.toml")
            assert get_logging_settings().log_level == "WARNING"
