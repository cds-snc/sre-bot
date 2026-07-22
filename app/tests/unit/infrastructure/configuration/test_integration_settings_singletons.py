"""Unit tests for integration settings singleton providers (PR-2)."""

from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings
from infrastructure.configuration.integrations.google import (
    GoogleResourcesConfig,
    GoogleWorkspaceSettings,
    get_google_resources_config,
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations.maxmind import (
    MaxMindSettings,
    get_maxmind_settings,
)
from infrastructure.configuration.integrations.notify import (
    NotifySettings,
    get_notify_settings,
)
from infrastructure.configuration.integrations.opsgenie import (
    OpsGenieSettings,
    get_opsgenie_settings,
)
from infrastructure.configuration.integrations.sentinel import (
    SentinelSettings,
    get_sentinel_settings,
)
from infrastructure.configuration.integrations.slack import (
    SlackSettings,
    get_slack_settings,
)
from infrastructure.configuration.integrations.trello import (
    TrelloSettings,
    get_trello_settings,
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


class TestAwsSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_aws_settings.cache_clear()
        assert get_aws_settings() is get_aws_settings()

    def test_has_required_model_config(self):
        config = AwsSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        settings = AwsSettings()
        assert settings.AWS_REGION == "us-east-1"


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


class TestMaxMindSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_maxmind_settings.cache_clear()
        assert get_maxmind_settings() is get_maxmind_settings()

    def test_has_required_model_config(self):
        config = MaxMindSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("MAXMIND_DB_PATH", "/custom/path/GeoLite2-City.mmdb")
        settings = MaxMindSettings()
        assert settings.MAXMIND_DB_PATH == "/custom/path/GeoLite2-City.mmdb"


class TestNotifySettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_notify_settings.cache_clear()
        assert get_notify_settings() is get_notify_settings()

    def test_has_required_model_config(self):
        config = NotifySettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_API_URL", "https://notify.example.com")
        settings = NotifySettings()
        assert settings.NOTIFY_API_URL == "https://notify.example.com"


class TestOpsGenieSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_opsgenie_settings.cache_clear()
        assert get_opsgenie_settings() is get_opsgenie_settings()

    def test_has_required_model_config(self):
        config = OpsGenieSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("OPSGENIE_INTEGRATIONS_KEY", "test-key")
        settings = OpsGenieSettings()
        assert settings.OPSGENIE_INTEGRATIONS_KEY == "test-key"


class TestSentinelSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_sentinel_settings.cache_clear()
        assert get_sentinel_settings() is get_sentinel_settings()

    def test_has_required_model_config(self):
        config = SentinelSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SENTINEL_CUSTOMER_ID", "workspace-id")
        settings = SentinelSettings()
        assert settings.SENTINEL_CUSTOMER_ID == "workspace-id"


class TestTrelloSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_trello_settings.cache_clear()
        assert get_trello_settings() is get_trello_settings()

    def test_has_required_model_config(self):
        config = TrelloSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("TRELLO_APP_KEY", "trello-key-123")
        settings = TrelloSettings()
        assert settings.TRELLO_APP_KEY == "trello-key-123"
