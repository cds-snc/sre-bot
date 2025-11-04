"""Unit tests for groups module normalization helper functions.

Tests cover:
- map_normalized_groups_to_providers() - Map groups to providers by prefix
- normalize_member_for_provider() - Normalize member email to provider-specific format

All tests use pure functions with mocked dependencies.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from modules.groups import mappings as gm
from modules.groups import service as gs
from modules.groups.models import NormalizedMember


@pytest.mark.unit
class TestMapNormalizedGroupsToProviders:
    """Tests for map_normalized_groups_to_providers() function."""

    def test_basic_grouping_by_provider(self):
        """map_normalized_groups_to_providers groups by provider attribute."""
        groups = [
            {"id": "g1", "provider": "aws"},
            {"id": "g2", "provider": "google"},
            {"id": "g3", "provider": "aws"},
        ]
        result = gm.map_normalized_groups_to_providers(groups)
        assert "aws" in result
        assert "google" in result
        assert len(result["aws"]) == 2
        assert len(result["google"]) == 1

    def test_groups_without_provider_go_to_unknown(self):
        """map_normalized_groups_to_providers puts groups without provider in 'unknown'."""
        groups = [
            {"id": "g1", "provider": "aws"},
            {"id": "g2"},  # No provider
            {"id": "g3", "provider": None},
        ]
        result = gm.map_normalized_groups_to_providers(groups)
        assert "unknown" in result
        assert len(result["unknown"]) == 2

    def test_handles_dict_and_object_groups(self):
        """map_normalized_groups_to_providers handles both dict and object groups."""
        dict_group = {"id": "g1", "provider": "aws"}
        obj_group = SimpleNamespace(id="g2", provider="google")

        groups = [dict_group, obj_group]
        result = gm.map_normalized_groups_to_providers(groups)

        assert len(result["aws"]) == 1
        assert len(result["google"]) == 1
        assert isinstance(result["aws"][0], dict)
        assert isinstance(result["google"][0], SimpleNamespace)

    def test_associate_false_no_prefix_detection(self):
        """map_normalized_groups_to_providers ignores prefixes when associate=False."""
        groups = [{"id": "a-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(groups, associate=False)

        assert "unknown" in result
        assert result["unknown"][0]["provider"] == "unknown"

    @patch("modules.groups.mappings.get_active_providers")
    def test_associate_true_detects_prefix(self, mock_get_active):
        """map_normalized_groups_to_providers updates provider when associate=True."""
        mock_get_active.return_value = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        groups = [{"id": "a-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(groups, associate=True)

        assert "aws" in result
        assert result["aws"][0]["provider"] == "aws"

    def test_associate_with_explicit_provider_registry(self):
        """map_normalized_groups_to_providers uses provided provider_registry."""
        provs = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        groups = [{"id": "a-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "aws" in result
        assert result["aws"][0]["provider"] == "aws"

    def test_associate_prefers_longest_prefix(self):
        """map_normalized_groups_to_providers uses longest matching prefix."""
        provs = {
            "a": SimpleNamespace(prefix="a"),
            "ab": SimpleNamespace(prefix="ab"),
        }
        groups = [{"id": "ab-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "ab" in result
        assert len(result["ab"]) == 1

    def test_associate_uses_provider_name_when_prefix_missing(self):
        """map_normalized_groups_to_providers uses provider name as prefix if not set."""
        provs = {
            "aws": SimpleNamespace(),  # No prefix attribute
            "google": SimpleNamespace(prefix="g"),
        }
        groups = [{"id": "aws-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "aws" in result
        assert result["aws"][0]["provider"] == "aws"

    def test_associate_handles_invalid_primary_name(self):
        """map_normalized_groups_to_providers handles unparseable primary names."""
        provs = {"aws": SimpleNamespace(prefix="a")}
        groups = [{"id": "", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "unknown" in result

    def test_associate_handles_immutable_objects(self):
        """map_normalized_groups_to_providers gracefully handles immutable objects."""

        class FrozenGroup:
            def __init__(self, id):
                self._id = id

            @property
            def id(self):
                return self._id

            @property
            def provider(self):
                return "unknown"

        provs = {"aws": SimpleNamespace(prefix="a")}
        frozen = FrozenGroup("a-my-group")
        groups = [frozen]

        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        # Should still be grouped somewhere (likely unknown since mutation failed)
        assert any(len(v) > 0 for v in result.values())

    def test_associate_uses_name_fallback_for_id(self):
        """map_normalized_groups_to_providers falls back to 'name' when 'id' missing."""
        provs = {"aws": SimpleNamespace(prefix="a")}
        groups = [{"name": "a-my-group", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "aws" in result
        assert result["aws"][0]["provider"] == "aws"

    def test_associate_with_email_style_group_name(self):
        """map_normalized_groups_to_providers handles email-style group names."""
        provs = {"google": SimpleNamespace(prefix="g")}
        groups = [{"id": "g:mygroup@example.com", "provider": "unknown"}]
        result = gm.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "google" in result

    def test_empty_groups_list(self):
        """map_normalized_groups_to_providers handles empty groups list."""
        result = gm.map_normalized_groups_to_providers([])
        assert result == {}

    def test_multiple_groups_per_provider(self):
        """map_normalized_groups_to_providers properly collects multiple groups per provider."""
        groups = [
            {"id": "g1", "provider": "aws"},
            {"id": "g2", "provider": "aws"},
            {"id": "g3", "provider": "aws"},
        ]
        result = gm.map_normalized_groups_to_providers(groups)

        assert len(result["aws"]) == 3

    def test_preserves_group_data_in_result(self):
        """map_normalized_groups_to_providers preserves original group data."""
        groups = [
            {
                "id": "g1",
                "provider": "aws",
                "name": "MyGroup",
                "email": "mygroup@example.com",
            }
        ]
        result = gm.map_normalized_groups_to_providers(groups)

        returned_group = result["aws"][0]
        assert returned_group["id"] == "g1"
        assert returned_group["name"] == "MyGroup"
        assert returned_group["email"] == "mygroup@example.com"


@pytest.mark.unit
class TestNormalizeMemberForProvider:
    """Tests for normalize_member_for_provider() function."""

    def test_normalizes_valid_email(self):
        """normalize_member_for_provider normalizes valid email address."""
        result = gm.normalize_member_for_provider("user@example.com", "aws")
        assert isinstance(result, NormalizedMember)
        assert result.email == "user@example.com"
        assert result.id is None
        assert result.role is None

    def test_raises_on_missing_at_sign(self):
        """normalize_member_for_provider raises ValueError when email lacks @."""
        with pytest.raises(ValueError):
            gm.normalize_member_for_provider("no-at-sign", "aws")

    def test_raises_on_empty_email(self):
        """normalize_member_for_provider raises ValueError on empty email."""
        with pytest.raises(ValueError):
            gm.normalize_member_for_provider("", "aws")

    def test_raises_on_none_email(self):
        """normalize_member_for_provider raises ValueError on None email."""
        with pytest.raises(ValueError):
            gm.normalize_member_for_provider(None, "aws")

    def test_accepts_various_email_formats(self):
        """normalize_member_for_provider accepts various valid email formats."""
        emails = [
            "user@example.com",
            "first.last@company.org",
            "user+tag@domain.co.uk",
            "a@b.c",
        ]
        for email in emails:
            result = gm.normalize_member_for_provider(email, "aws")
            assert result.email == email

    def test_works_with_different_providers(self):
        """normalize_member_for_provider works with different provider types."""
        providers = ["aws", "google", "okta", "azure"]
        for provider in providers:
            result = gm.normalize_member_for_provider("user@example.com", provider)
            assert result.email == "user@example.com"

    def test_returns_correct_normalized_member_structure(self):
        """normalize_member_for_provider returns NormalizedMember with correct structure."""
        result = gm.normalize_member_for_provider("test@example.com", "aws")
        assert isinstance(result, NormalizedMember)
        assert hasattr(result, "email")
        assert hasattr(result, "id")
        assert hasattr(result, "role")
        assert hasattr(result, "provider_member_id")
        assert hasattr(result, "raw")

    def test_service_wrapper_calls_mappings(self):
        """Service wrapper normalize_member_for_provider delegates to mappings."""
        result = gs.normalize_member_for_provider("user@example.com", "aws")
        assert isinstance(result, NormalizedMember)
        assert result.email == "user@example.com"

    def test_preserves_email_case(self):
        """normalize_member_for_provider preserves email case."""
        result = gm.normalize_member_for_provider("User@Example.COM", "aws")
        assert result.email == "User@Example.COM"

    def test_handles_email_with_special_characters(self):
        """normalize_member_for_provider handles emails with special characters."""
        special_emails = [
            "user+tag@example.com",
            "user_underscore@example.com",
            "user-dash@example.com",
            "123numeric@example.com",
        ]
        for email in special_emails:
            result = gm.normalize_member_for_provider(email, "aws")
            assert result.email == email


@pytest.mark.unit
class TestMapNormalizedGroupsServiceWrapper:
    """Tests for service wrapper map_normalized_groups_to_providers()."""

    def test_service_wrapper_delegates_to_mappings(self):
        """Service wrapper delegates to mappings module."""
        groups = [
            {"id": "g1", "provider": "aws"},
            {"id": "g2", "provider": "google"},
        ]
        result = gs.map_normalized_groups_to_providers(groups)

        assert "aws" in result
        assert "google" in result
        assert len(result["aws"]) == 1
        assert len(result["google"]) == 1

    def test_service_wrapper_supports_associate_param(self):
        """Service wrapper supports associate parameter."""
        groups = [{"id": "g1", "provider": "unknown"}]
        result = gs.map_normalized_groups_to_providers(groups, associate=False)

        assert "unknown" in result

    def test_service_wrapper_supports_provider_registry_param(self):
        """Service wrapper supports provider_registry parameter."""
        provs = {"aws": SimpleNamespace(prefix="a")}
        groups = [{"id": "a-g1", "provider": "unknown"}]
        result = gs.map_normalized_groups_to_providers(
            groups, associate=True, provider_registry=provs
        )

        assert "aws" in result
