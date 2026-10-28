"""Tests for refactored settings structure.

Verifies the domain-based organization of settings modules after Phase 1
refactoring (split by domain pattern).
"""

import infrastructure.configuration.base as configuration_base
from infrastructure.configuration.base import FeatureSettings
from infrastructure.configuration.features import (
    AtipSettings,
    AWSFeatureSettings,
    IncidentFeatureSettings,
    SreOpsSettings,
)
from infrastructure.configuration.features.aws_ops import (
    get_aws_feature_settings,
)


class TestSettingsStructure:
    """Test the new domain-based settings structure."""

    def test_settings_loads_all_feature_sections(self):
        """Verify feature settings provider loads correctly."""
        aws_feature_settings = get_aws_feature_settings()

        assert isinstance(aws_feature_settings, AWSFeatureSettings)
        assert hasattr(aws_feature_settings, "AWS_ADMIN_GROUPS")

    def test_settings_singleton_still_works(self):
        """Verify provider singleton behavior is preserved."""
        aws_feature_settings1 = get_aws_feature_settings()
        aws_feature_settings2 = get_aws_feature_settings()

        assert aws_feature_settings1 is aws_feature_settings2

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

    def test_no_infrastructure_settings_base_remains(self):
        """Every hosting slice reads the configuration files, so the flat-name base class is gone."""
        assert not hasattr(configuration_base, "InfrastructureSettings")
