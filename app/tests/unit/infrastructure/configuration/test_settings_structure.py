"""Tests for refactored settings structure.

Verifies the domain-based organization of settings modules after Phase 1
refactoring (split by domain pattern).
"""

from infrastructure.services.providers import get_settings
from infrastructure.configuration import RetrySettings
from infrastructure.configuration.base import (
    IntegrationSettings,
    FeatureSettings,
    InfrastructureSettings,
)
from infrastructure.configuration.integrations import (
    SlackSettings,
    AwsSettings,
    GoogleWorkspaceSettings,
    GoogleResourcesConfig,
    MaxMindSettings,
    NotifySettings,
    OpsGenieSettings,
    SentinelSettings,
    TrelloSettings,
)
from infrastructure.configuration.features import (
    GroupsFeatureSettings,
    CommandsSettings,
    IncidentFeatureSettings,
    AWSFeatureSettings,
    AtipSettings,
    SreOpsSettings,
)
from infrastructure.configuration.infrastructure import (
    IdempotencySettings,
    ServerSettings,
    DevSettings,
)


class TestSettingsStructure:
    """Test the new domain-based settings structure."""

    def test_settings_loads_all_integration_sections(self):
        """Verify all integration settings sections load correctly."""
        settings = get_settings()
        # Integration settings
        assert hasattr(settings, "slack")
        assert hasattr(settings, "aws")
        assert hasattr(settings, "google_workspace")
        assert hasattr(settings, "google_resources")
        assert hasattr(settings, "maxmind")
        assert hasattr(settings, "notify")
        assert hasattr(settings, "opsgenie")
        assert hasattr(settings, "sentinel")
        assert hasattr(settings, "trello")

    def test_settings_loads_all_feature_sections(self):
        """Verify all feature settings sections load correctly."""
        settings = get_settings()
        # Feature settings
        assert hasattr(settings, "groups")
        assert hasattr(settings, "commands")
        assert hasattr(settings, "feat_incident")
        assert hasattr(settings, "aws_feature")
        assert hasattr(settings, "atip")
        assert hasattr(settings, "sre_ops")

    def test_settings_loads_all_infrastructure_sections(self):
        """Verify all infrastructure settings sections load correctly."""
        settings = get_settings()
        # Infrastructure settings
        assert hasattr(settings, "retry")
        assert hasattr(settings, "idempotency")
        assert hasattr(settings, "server")
        assert hasattr(settings, "dev")

    def test_settings_preserves_field_access(self):
        """Verify settings values are accessible at same paths as before."""
        settings = get_settings()
        assert hasattr(settings.slack, "SLACK_TOKEN")
        assert hasattr(settings.aws, "AWS_REGION")
        assert hasattr(settings.google_workspace, "GOOGLE_DELEGATED_ADMIN_EMAIL")

        # Feature fields
        assert hasattr(settings.groups, "providers")
        assert hasattr(settings.groups, "circuit_breaker_enabled")
        assert hasattr(settings.commands, "providers")

        # Infrastructure fields
        assert hasattr(settings.retry, "enabled")
        assert hasattr(settings.retry, "backend")
        assert hasattr(settings.idempotency, "IDEMPOTENCY_TTL_SECONDS")

    def test_retry_settings_can_be_imported_separately(self):
        """Verify RetrySettings can be imported separately for testing."""
        retry = RetrySettings()
        assert retry.enabled is not None
        assert retry.backend in ["memory", "dynamodb", "sqs"]
        assert retry.max_attempts >= 1
        assert retry.base_delay_seconds >= 1
        assert retry.max_delay_seconds >= retry.base_delay_seconds

    def test_settings_is_production_property(self):
        """Verify is_production property works correctly."""
        settings = get_settings()
        # Production is when PREFIX is empty
        assert hasattr(settings, "is_production")
        assert isinstance(settings.is_production, bool)

    def test_settings_classes_have_proper_base_classes(self):
        """Verify settings classes inherit from appropriate base classes."""
        # Check inheritance
        assert issubclass(SlackSettings, IntegrationSettings)
        assert issubclass(GroupsFeatureSettings, FeatureSettings)
        assert issubclass(RetrySettings, InfrastructureSettings)

    def test_settings_singleton_still_works(self):
        """Verify settings singleton behavior is preserved."""
        # Settings should be a single instance from get_settings
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_all_integration_settings_classes_instantiable(self):
        """Verify all integration settings classes can be instantiated."""
        # Test that all integration settings classes are functional
        instances = [
            SlackSettings(),
            AwsSettings(),
            GoogleWorkspaceSettings(),
            GoogleResourcesConfig(),
            MaxMindSettings(),
            NotifySettings(),
            OpsGenieSettings(),
            SentinelSettings(),
            TrelloSettings(),
        ]

        # Verify they are all instances of IntegrationSettings
        for instance in instances:
            assert isinstance(instance, IntegrationSettings)

    def test_all_feature_settings_classes_instantiable(self):
        """Verify all feature settings classes can be instantiated."""
        # Test that all feature settings classes are functional
        instances = [
            GroupsFeatureSettings(),
            CommandsSettings(),
            IncidentFeatureSettings(),
            AWSFeatureSettings(),
            AtipSettings(),
            SreOpsSettings(),
        ]

        # Verify they are all instances of FeatureSettings
        for instance in instances:
            assert isinstance(instance, FeatureSettings)

    def test_all_infrastructure_settings_classes_instantiable(self):
        """Verify all infrastructure settings classes can be instantiated."""
        # Test that all infrastructure settings classes are functional
        instances = [
            IdempotencySettings(),
            RetrySettings(),
            ServerSettings(),
            DevSettings(),
        ]

        # Verify they are all instances of InfrastructureSettings
        for instance in instances:
            assert isinstance(instance, InfrastructureSettings)
