"""Unit tests for the Slack and Google integration settings singleton providers."""

from infrastructure.configuration.integrations.google import (
    GoogleResourcesConfig,
    GoogleWorkspaceSettings,
    get_google_resources_config,
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations.slack import (
    SlackSettings,
    get_slack_settings,
)


class TestSlackSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_slack_settings.cache_clear()
        assert get_slack_settings() is get_slack_settings()

    def test_has_required_model_config(self):
        config = SlackSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_TOKEN", "xoxb-test")
        settings = SlackSettings()
        assert settings.SLACK_TOKEN == "xoxb-test"


class TestGoogleWorkspaceSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_google_workspace_settings.cache_clear()
        assert get_google_workspace_settings() is get_google_workspace_settings()

    def test_has_required_model_config(self):
        config = GoogleWorkspaceSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_DELEGATED_ADMIN_EMAIL", "admin@example.com")
        settings = GoogleWorkspaceSettings()
        assert settings.GOOGLE_DELEGATED_ADMIN_EMAIL == "admin@example.com"


class TestGoogleResourcesConfigSingleton:
    def test_singleton_returns_same_instance(self):
        get_google_resources_config.cache_clear()
        assert get_google_resources_config() is get_google_resources_config()

    def test_has_required_model_config(self):
        config = GoogleResourcesConfig.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_RESOURCES", '{"inc": {"d": "drive-id"}}')
        settings = GoogleResourcesConfig()
        assert settings.incident_drive_id == "drive-id"
