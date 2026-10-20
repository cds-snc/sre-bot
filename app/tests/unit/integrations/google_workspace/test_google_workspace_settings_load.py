"""Unit tests for loading the Google Workspace vendor settings slice.

Settings are built from monkeypatched environment variables with the .env file
disabled, so the assertions see only the values the test sets. Each field reads
the flat environment name it always has; the provider is a cached singleton.
"""

import pytest
from pydantic import ValidationError

from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings

pytestmark = pytest.mark.unit


@pytest.fixture
def google_unused(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
        "GOOGLE_WORKSPACE_CUSTOMER_ID",
        "GOOGLE_DELEGATED_ADMIN_EMAIL",
        "SRE_BOT_EMAIL",
        "GOOGLE_API_NUM_RETRIES",
        "GOOGLE_API_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_provider_returns_one_cached_instance() -> None:
    """Every caller shares one slice, so it is built and validated once."""
    get_google_workspace_settings.cache_clear()

    assert get_google_workspace_settings() is get_google_workspace_settings()


def test_slice_reads_the_env_file_case_sensitively_and_ignores_unknown_keys() -> None:
    """The slice keeps the shared .env loading rules of the vendor slices."""
    config = GoogleWorkspaceSettings.model_config

    assert (config.get("env_file"), config.get("case_sensitive"), config.get("extra")) == (".env", True, "ignore")


@pytest.mark.usefixtures("google_unused")
def test_defaults_apply_while_google_is_not_configured() -> None:
    """Without any Google variable the slice builds with its defaults."""
    settings = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert (
        settings.GOOGLE_DELEGATED_ADMIN_EMAIL,
        settings.SRE_BOT_EMAIL,
        settings.GOOGLE_WORKSPACE_CUSTOMER_ID,
        settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE,
        settings.GOOGLE_API_NUM_RETRIES,
        settings.GOOGLE_API_TIMEOUT_SECONDS,
    ) == ("", "", "my_customer", "", 3, 10.0)


@pytest.mark.usefixtures("google_unused")
def test_fields_read_their_flat_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment names are unchanged by the move."""
    monkeypatch.setenv("GOOGLE_DELEGATED_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("SRE_BOT_EMAIL", "bot@example.com")
    monkeypatch.setenv("GOOGLE_API_NUM_RETRIES", "5")
    monkeypatch.setenv("GOOGLE_API_TIMEOUT_SECONDS", "2.5")

    settings = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert (
        settings.GOOGLE_DELEGATED_ADMIN_EMAIL,
        settings.SRE_BOT_EMAIL,
        settings.GOOGLE_API_NUM_RETRIES,
        settings.GOOGLE_API_TIMEOUT_SECONDS,
    ) == ("admin@example.com", "bot@example.com", 5, 2.5)


@pytest.mark.usefixtures("google_unused")
@pytest.mark.parametrize("timeout", ["0", "-1"])
def test_a_non_positive_timeout_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch, timeout: str) -> None:
    """A timeout must be positive, so zero and negative values fail validation."""
    monkeypatch.setenv("GOOGLE_API_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError, match="GOOGLE_API_TIMEOUT_SECONDS"):
        GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]
