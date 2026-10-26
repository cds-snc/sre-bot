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
import svcs
from fastapi import FastAPI

from contracts.configuration import ConfigurationError, HostInfo, installed_configuration_files
from infrastructure.logging.settings import LoggingSettings, get_logging_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration import CONFIG_DIR as REAL_CONFIG_DIR
from server.configuration import get_server_settings, load_host_configuration
from server.lifespan import build_lifespan
from server.plugins.settings import PluginsSettings, get_plugins_settings
from server.slack.settings import get_slack_transport_settings
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the loader at tmp_path and build the logging slice fresh for each test."""
    monkeypatch.setattr("server.configuration.loader.CONFIG_DIR", tmp_path)
    (tmp_path / "base.toml").write_text((REAL_CONFIG_DIR / "base.toml").read_text(encoding="utf-8"), encoding="utf-8")
    for getter in (get_server_settings, get_notify_api_key_leak_settings, get_slack_transport_settings, get_plugins_settings):
        getter.cache_clear()
    monkeypatch.setitem(LoggingSettings.model_config, "env_file", None)
    monkeypatch.setitem(PluginsSettings.model_config, "env_file", None)
    get_logging_settings.cache_clear()
    yield tmp_path
    get_logging_settings.cache_clear()
    get_plugins_settings.cache_clear()


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
    (_config_dir / "ci.toml").write_text('[logging]\nlog_levle = "DEBUG"\n', encoding="utf-8")

    await _boot_fails_naming(str(_config_dir / "ci.toml"), "[logging]", "log_levle")


async def test_missing_environment_file_fails_boot_naming_it(_config_dir: Path) -> None:

    await _boot_fails_naming(str(_config_dir / "ci.toml"))


async def test_valid_files_are_installed_before_the_logging_slice_is_built(_config_dir: Path) -> None:
    (_config_dir / "ci.toml").write_text('[logging]\nlog_level = "WARNING"\n', encoding="utf-8")

    with ExitStack() as stack:
        _stub_later_phases(stack)
        async with lifespan(FastAPI()):
            assert installed_configuration_files().paths == (_config_dir / "base.toml", _config_dir / "ci.toml")
            assert get_logging_settings().log_level == "WARNING"


async def test_lifespan_does_not_load_or_install_configuration_files(_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The factory ran the configuration phase; the lifespan only reads what it loaded."""
    (_config_dir / "ci.toml").write_text("", encoding="utf-8")
    configuration = load_host_configuration()
    load_spy = MagicMock()
    install_spy = MagicMock()
    monkeypatch.setattr("server.configuration.host_configuration.load_configuration_files", load_spy)
    monkeypatch.setattr("server.configuration.host_configuration.install_configuration_files", install_spy)

    with ExitStack() as stack:
        _stub_later_phases(stack)
        app = FastAPI()
        async with build_lifespan(configuration)(app):
            assert app.state.host_info is configuration.host_info

    load_spy.assert_not_called()
    install_spy.assert_not_called()


async def test_lifespan_registers_host_info_in_the_service_registry(_config_dir: Path) -> None:
    """New code resolves HostInfo by contract from the registry; it is the instance the factory built."""
    (_config_dir / "ci.toml").write_text("", encoding="utf-8")
    configuration = load_host_configuration()

    with ExitStack() as stack:
        _stub_later_phases(stack)
        app = FastAPI()
        async with build_lifespan(configuration)(app):
            container = svcs.Container(app.state.svcs_registry)
            assert container.get(HostInfo) is configuration.host_info


async def test_an_installed_entry_point_without_an_enablement_key_fails_boot_naming_it(_config_dir: Path) -> None:
    base = _config_dir / "base.toml"
    base.write_text(base.read_text(encoding="utf-8").replace("rant = true\n", ""), encoding="utf-8")
    (_config_dir / "ci.toml").write_text("", encoding="utf-8")

    await _boot_fails_naming("'rant' has no enablement key")


async def test_the_lifespan_loads_plugins_with_the_disabled_names_from_the_files(_config_dir: Path) -> None:
    (_config_dir / "ci.toml").write_text("", encoding="utf-8")
    configuration = load_host_configuration()

    with ExitStack() as stack:
        _stub_later_phases(stack)
        load_plugins = stack.enter_context(patch("server.lifespan.load_plugins"))
        async with build_lifespan(configuration)(FastAPI()):
            pass

    assert configuration.disabled_plugins == frozenset({"access.catalog", "access.request", "access.sync"})
    assert load_plugins.call_args.args[1] == configuration.disabled_plugins
