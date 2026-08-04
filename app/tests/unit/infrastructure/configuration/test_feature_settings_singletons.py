"""Unit tests for feature settings singleton providers (PR-4)."""

from infrastructure.configuration.features.atip import (
    AtipSettings,
    get_atip_settings,
)
from infrastructure.configuration.features.aws_ops import (
    AWSFeatureSettings,
    get_aws_feature_settings,
)
from infrastructure.configuration.features.groups import (
    GroupsFeatureSettings,
    get_groups_settings,
)
from infrastructure.configuration.features.incident import (
    IncidentFeatureSettings,
    get_incident_settings,
)
from infrastructure.configuration.features.sre_ops import (
    SreOpsSettings,
    get_sre_ops_settings,
)


class TestGroupsFeatureSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_groups_settings.cache_clear()
        assert get_groups_settings() is get_groups_settings()

    def test_has_required_model_config(self):
        config = GroupsFeatureSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("GROUP_DOMAIN", "example.com")
        settings = GroupsFeatureSettings()
        assert settings.group_domain == "example.com"


class TestIncidentFeatureSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_incident_settings.cache_clear()
        assert get_incident_settings() is get_incident_settings()

    def test_has_required_model_config(self):
        config = IncidentFeatureSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("INCIDENT_CHANNEL", "C_INCIDENT")
        settings = IncidentFeatureSettings()
        assert settings.INCIDENT_CHANNEL == "C_INCIDENT"


class TestAWSFeatureSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_aws_feature_settings.cache_clear()
        assert get_aws_feature_settings() is get_aws_feature_settings()

    def test_has_required_model_config(self):
        config = AWSFeatureSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_OPS_GROUP_NAME", "aws-ops-team")
        settings = AWSFeatureSettings()
        assert settings.AWS_OPS_GROUP_NAME == "aws-ops-team"


class TestAtipSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_atip_settings.cache_clear()
        assert get_atip_settings() is get_atip_settings()

    def test_has_required_model_config(self):
        config = AtipSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("ATIP_ANNOUNCE_CHANNEL", "C_ATIP")
        settings = AtipSettings()
        assert settings.ATIP_ANNOUNCE_CHANNEL == "C_ATIP"


class TestSreOpsSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_sre_ops_settings.cache_clear()
        assert get_sre_ops_settings() is get_sre_ops_settings()

    def test_has_required_model_config(self):
        config = SreOpsSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SRE_OPS_CHANNEL_ID", "C_SRE")
        settings = SreOpsSettings()
        assert settings.SRE_OPS_CHANNEL_ID == "C_SRE"
