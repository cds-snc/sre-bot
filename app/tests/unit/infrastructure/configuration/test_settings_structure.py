"""Tests for refactored settings structure.

Verifies the domain-based organization of settings modules after Phase 1
refactoring (split by domain pattern).
"""

from infrastructure.configuration.app import get_app_settings
from infrastructure.configuration.base import (
    FeatureSettings,
    IntegrationSettings,
    InfrastructureSettings,
)
from infrastructure.configuration.features.aws_ops import (
    get_aws_feature_settings,
)
from infrastructure.configuration.infrastructure.retry import (
    RetrySettings,
    get_retry_settings,
)
from infrastructure.configuration.infrastructure.server import (
    get_server_settings,
)
from infrastructure.configuration.integrations.google import (
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations import (
    AwsSettings,
    GoogleWorkspaceSettings,
    GoogleResourcesConfig,
    MaxMindSettings,
    NotifySettings,
    SlackSettings,
    OpsGenieSettings,
    SentinelSettings,
    TrelloSettings,
)
from infrastructure.configuration.features import (
    AWSFeatureSettings,
    AtipSettings,
    IncidentFeatureSettings,
    SreOpsSettings,
)
from infrastructure.configuration.infrastructure import (
    DevSettings,
    IdempotencySettings,
    ServerSettings,
)


class TestSettingsStructure:
    """Test the new domain-based settings structure."""

    def test_settings_loads_all_integration_sections(self):
        """Verify integration settings provider loads correctly."""
        google_workspace_settings = get_google_workspace_settings()

        assert isinstance(google_workspace_settings, GoogleWorkspaceSettings)
        assert hasattr(google_workspace_settings, "SRE_BOT_EMAIL")

    def test_settings_loads_all_feature_sections(self):
        """Verify feature settings provider loads correctly."""
        aws_feature_settings = get_aws_feature_settings()

        assert isinstance(aws_feature_settings, AWSFeatureSettings)
        assert hasattr(aws_feature_settings, "AWS_ADMIN_GROUPS")

    def test_settings_loads_all_infrastructure_sections(self):
        """Verify infrastructure settings providers load correctly."""
        server_settings = get_server_settings()
        retry_settings = get_retry_settings()

        assert isinstance(server_settings, ServerSettings)
        assert isinstance(retry_settings, RetrySettings)

    def test_settings_preserves_field_access(self):
        """Verify settings values are accessible from narrow providers."""
        aws_feature_settings = get_aws_feature_settings()
        server_settings = get_server_settings()
        google_workspace_settings = get_google_workspace_settings()
        retry_settings = get_retry_settings()

        assert hasattr(aws_feature_settings, "AWS_ADMIN_GROUPS")
        assert hasattr(server_settings, "BACKEND_URL")
        assert hasattr(
            google_workspace_settings,
            "GOOGLE_DELEGATED_ADMIN_EMAIL",
        )
        assert hasattr(retry_settings, "enabled")
        assert hasattr(retry_settings, "backend")

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
        settings = get_app_settings()
        # Production is when PREFIX is empty
        assert hasattr(settings, "is_production")
        assert isinstance(settings.is_production, bool)

    def test_settings_classes_have_proper_base_classes(self):
        """Verify settings classes inherit from appropriate base classes."""
        # Check inheritance
        assert issubclass(SlackSettings, IntegrationSettings)
        assert issubclass(RetrySettings, InfrastructureSettings)

    def test_settings_singleton_still_works(self):
        """Verify provider singleton behavior is preserved."""
        retry_settings1 = get_retry_settings()
        retry_settings2 = get_retry_settings()
        server_settings1 = get_server_settings()
        server_settings2 = get_server_settings()
        google_settings1 = get_google_workspace_settings()
        google_settings2 = get_google_workspace_settings()
        aws_feature_settings1 = get_aws_feature_settings()
        aws_feature_settings2 = get_aws_feature_settings()

        assert retry_settings1 is retry_settings2
        assert server_settings1 is server_settings2
        assert google_settings1 is google_settings2
        assert aws_feature_settings1 is aws_feature_settings2

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

    def test_google_workspace_settings_defaults_customer_id(self, monkeypatch):
        """Verify Google Workspace customer ID defaults to the stable alias."""
        monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)

        settings = GoogleWorkspaceSettings.model_validate({})

        assert settings.GOOGLE_WORKSPACE_CUSTOMER_ID == "my_customer"

    def test_all_feature_settings_classes_instantiable(self):
        """Verify all feature settings classes can be instantiated."""
        # Test that all feature settings classes are functional
        instances = [
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
