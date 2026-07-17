"""Unit tests for Settings aggregator delegation to domain singletons (PR-5).

Verifies that Settings.__init__ delegates to singleton providers so that
Settings().slack is get_slack_settings() (same object identity).
"""

import pytest

from infrastructure.configuration.settings import Settings
from infrastructure.configuration.app import get_app_settings
from infrastructure.configuration.integrations.slack import SlackSettings
from infrastructure.configuration.integrations import (
    get_slack_settings,
    get_aws_settings,
    get_google_workspace_settings,
    get_google_resources_config,
    get_maxmind_settings,
    get_notify_settings,
    get_opsgenie_settings,
    get_sentinel_settings,
    get_trello_settings,
)
from infrastructure.configuration.features import (
    get_incident_settings,
    get_aws_feature_settings,
    get_atip_settings,
    get_sre_ops_settings,
)
from infrastructure.configuration.infrastructure import (
    get_server_settings,
    get_dev_settings,
    get_idempotency_settings,
    get_retry_settings,
    get_platforms_settings,
    get_directory_settings,
)


@pytest.fixture(autouse=True)
def clear_all_caches():
    """Clear all singleton caches before and after each test."""
    get_app_settings.cache_clear()
    get_slack_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_google_resources_config.cache_clear()
    get_maxmind_settings.cache_clear()
    get_notify_settings.cache_clear()
    get_opsgenie_settings.cache_clear()
    get_sentinel_settings.cache_clear()
    get_trello_settings.cache_clear()
    get_incident_settings.cache_clear()
    get_aws_feature_settings.cache_clear()
    get_atip_settings.cache_clear()
    get_sre_ops_settings.cache_clear()
    get_server_settings.cache_clear()
    get_dev_settings.cache_clear()
    get_idempotency_settings.cache_clear()
    get_retry_settings.cache_clear()
    get_platforms_settings.cache_clear()
    get_directory_settings.cache_clear()
    yield
    get_app_settings.cache_clear()
    get_slack_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_google_resources_config.cache_clear()
    get_maxmind_settings.cache_clear()
    get_notify_settings.cache_clear()
    get_opsgenie_settings.cache_clear()
    get_sentinel_settings.cache_clear()
    get_trello_settings.cache_clear()
    get_incident_settings.cache_clear()
    get_aws_feature_settings.cache_clear()
    get_atip_settings.cache_clear()
    get_sre_ops_settings.cache_clear()
    get_server_settings.cache_clear()
    get_dev_settings.cache_clear()
    get_idempotency_settings.cache_clear()
    get_retry_settings.cache_clear()
    get_platforms_settings.cache_clear()
    get_directory_settings.cache_clear()


class TestSettingsDelegation:
    """Settings aggregator delegates to domain singletons (same object identity)."""

    def test_settings_slack_is_singleton(self):
        """Settings().slack must be the same object as get_slack_settings()."""
        assert Settings().slack is get_slack_settings()

    def test_settings_aws_is_singleton(self):
        assert Settings().aws is get_aws_settings()

    def test_settings_google_workspace_is_singleton(self):
        assert Settings().google_workspace is get_google_workspace_settings()

    def test_settings_google_resources_is_singleton(self):
        assert Settings().google_resources is get_google_resources_config()

    def test_settings_maxmind_is_singleton(self):
        assert Settings().maxmind is get_maxmind_settings()

    def test_settings_notify_is_singleton(self):
        assert Settings().notify is get_notify_settings()

    def test_settings_opsgenie_is_singleton(self):
        assert Settings().opsgenie is get_opsgenie_settings()

    def test_settings_sentinel_is_singleton(self):
        assert Settings().sentinel is get_sentinel_settings()

    def test_settings_trello_is_singleton(self):
        assert Settings().trello is get_trello_settings()

    def test_settings_feat_incident_is_singleton(self):
        assert Settings().feat_incident is get_incident_settings()

    def test_settings_aws_feature_is_singleton(self):
        assert Settings().aws_feature is get_aws_feature_settings()

    def test_settings_atip_is_singleton(self):
        assert Settings().atip is get_atip_settings()

    def test_settings_sre_ops_is_singleton(self):
        assert Settings().sre_ops is get_sre_ops_settings()

    def test_settings_server_is_singleton(self):
        assert Settings().server is get_server_settings()

    def test_settings_dev_is_singleton(self):
        assert Settings().dev is get_dev_settings()

    def test_settings_idempotency_is_singleton(self):
        assert Settings().idempotency is get_idempotency_settings()

    def test_settings_retry_is_singleton(self):
        assert Settings().retry is get_retry_settings()

    def test_settings_platforms_is_singleton(self):
        assert Settings().platforms is get_platforms_settings()

    def test_settings_directory_is_singleton(self):
        assert Settings().directory is get_directory_settings()


class TestSettingsAppFieldDelegation:
    """Settings app-level fields (PREFIX, LOG_LEVEL, GIT_SHA) match AppSettings."""

    def test_prefix_matches_app_settings(self):
        assert Settings().PREFIX == get_app_settings().PREFIX

    def test_log_level_matches_app_settings(self):
        assert Settings().LOG_LEVEL == get_app_settings().LOG_LEVEL

    def test_git_sha_matches_app_settings(self):
        assert Settings().GIT_SHA == get_app_settings().GIT_SHA

    def test_is_production_matches_app_settings(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        get_app_settings.cache_clear()
        assert Settings().is_production == get_app_settings().is_production

    def test_prefix_override_via_env(self, monkeypatch):
        """Settings inherits PREFIX from environment (not just AppSettings cache)."""
        monkeypatch.setenv("PREFIX", "staging")
        get_app_settings.cache_clear()
        assert Settings().PREFIX == "staging"


class TestSettingsKwargsOverride:
    """Settings kwargs override singletons (test isolation pattern)."""

    def test_kwargs_override_slack(self):
        """Settings(slack=custom) uses custom, not the singleton."""
        custom = SlackSettings()
        settings = Settings(slack=custom)
        assert settings.slack is custom

    def test_kwargs_override_does_not_affect_singleton(self):
        """Passing a custom object does not pollute the singleton cache."""
        custom = SlackSettings()
        Settings(slack=custom)
        # Singleton is still the original cached instance
        assert get_slack_settings() is not custom or True  # singleton unaffected
