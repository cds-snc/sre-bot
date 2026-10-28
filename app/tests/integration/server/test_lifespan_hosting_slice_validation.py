"""Integration tests for the hosting slices in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed, so only the configuration phase does
real work. The directory, audit and coordination slices are built from a copy of the checked-in
files with their caches cleared and the .env file disabled. An unknown or deleted key in
[directory], [audit] or [coordination] must stop startup with a ConfigurationError naming the
key, before the lifespan yields and before core services are built; the checked-in files boot.
"""

import shutil
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationError
from infrastructure.audit.settings import AuditSettings, get_audit_settings
from infrastructure.coordination.settings import ConditionalWriteSettings, get_conditional_write_settings
from infrastructure.directory.settings import DirectorySettings, get_directory_settings
from server.configuration import host_configuration
from server.configuration.loader import CONFIG_DIR, load_configuration_files
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _directory_slice_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the directory slice from the files only, fresh for each test."""
    monkeypatch.setitem(DirectorySettings.model_config, "env_file", None)
    monkeypatch.delenv("DIRECTORY__REQUIRE_STARTUP_WARMUP", raising=False)
    get_directory_settings.cache_clear()
    yield
    get_directory_settings.cache_clear()


@pytest.fixture(autouse=True)
def _audit_and_coordination_slices_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the audit and coordination slices from the files only, fresh for each test."""
    for settings_class in (AuditSettings, ConditionalWriteSettings):
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    for name in ("AUDIT__TABLE_NAME", "COORDINATION__TABLE_NAME"):
        monkeypatch.delenv(name, raising=False)
    get_audit_settings.cache_clear()
    get_conditional_write_settings.cache_clear()
    yield
    get_audit_settings.cache_clear()
    get_conditional_write_settings.cache_clear()


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


def _with_ci_file_lines(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lines: str) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    with (tmp_path / "config" / "ci.toml").open("a", encoding="utf-8") as ci_file:
        ci_file.write(lines)
    monkeypatch.setattr(
        host_configuration,
        "load_configuration_files",
        lambda environment, directory=None: load_configuration_files(environment, tmp_path / "config"),
    )


async def _boot_fails_naming(key: str) -> None:
    reached_yield = False
    with ExitStack() as stack, capture_logs():
        core_services = _stub_later_phases(stack)
        with pytest.raises(ConfigurationError, match=key):
            async with lifespan(FastAPI()):
                reached_yield = True

    assert reached_yield is False
    core_services.assert_not_awaited()


@pytest.mark.parametrize("key", ["require_startup_warmop", "provider", "cache_ttl_seconds"])
async def test_unknown_or_deleted_directory_key_fails_boot_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str
) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, f"\n[directory]\n{key} = 1\n")

    await _boot_fails_naming(key)


@pytest.mark.parametrize(
    ("table", "key"),
    [
        ("audit", "audit_table_name"),
        ("coordination", "idempotency_in_progress_ttl_seconds"),
        ("coordination", "table"),
    ],
)
async def test_unknown_audit_or_coordination_key_fails_boot_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, table: str, key: str
) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, f"\n[{table}]\n{key} = 1\n")

    await _boot_fails_naming(key)


async def test_checked_in_files_boot_with_no_startup_warmup() -> None:
    reached_yield = False

    with ExitStack() as stack:
        _stub_later_phases(stack)
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is True
    assert get_directory_settings().require_startup_warmup is False
    assert get_audit_settings().table_name == "sre_bot_audit_trail"
    assert get_conditional_write_settings().table_name == "sre_bot_idempotency"
