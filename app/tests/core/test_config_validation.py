import pytest

from core.config import GroupsFeatureSettings


def test_groups_feature_settings_multiple_primary_raises():
    providers = {
        "google": {"primary": True},
        "aws": {"primary": True},
    }

    with pytest.raises(ValueError):
        GroupsFeatureSettings(providers=providers)


def test_groups_feature_settings_single_primary_ok():
    providers = {
        "google": {"primary": True},
        "aws": {"prefix": "aws"},
    }

    s = GroupsFeatureSettings(providers=providers)
    assert isinstance(s.providers, dict)
    assert any(isinstance(v, dict) for v in s.providers.values())
