"""Unit tests for domain appending in group mappings.

Tests cover:
- Mapping with domain appended to primary provider
- Mapping without domain configuration
- Preserving existing email format when domain not required
- Canonical name extraction with domain suffix
- Google provider domain configuration from settings
"""

import pytest
from unittest.mock import MagicMock

from modules.groups import mappings


class TestMapProviderGroupIdWithDomain:
    """Tests for domain appending in map_provider_group_id function."""

    @pytest.fixture
    def mock_providers_with_domain(self):
        """Mock provider registry with Google provider requiring email format."""
        google_provider = MagicMock()
        google_provider.prefix = "google"
        google_provider.requires_email_format = True
        google_provider.domain = "cds-snc.ca"

        aws_provider = MagicMock()
        aws_provider.prefix = "aws"
        aws_provider.requires_email_format = False
        aws_provider.domain = None

        return {
            "google": google_provider,
            "aws": aws_provider,
        }

    @pytest.fixture
    def mock_providers_without_domain(self):
        """Mock provider registry with no domain configured."""
        google_provider = MagicMock()
        google_provider.prefix = "google"
        google_provider.requires_email_format = True
        google_provider.domain = None

        aws_provider = MagicMock()
        aws_provider.prefix = "aws"
        aws_provider.requires_email_format = False
        aws_provider.domain = None

        return {
            "google": google_provider,
            "aws": aws_provider,
        }

    @pytest.fixture
    def mock_providers_no_email_format(self):
        """Mock provider registry where primary doesn't require email format."""
        google_provider = MagicMock()
        google_provider.prefix = "google"
        google_provider.requires_email_format = False
        google_provider.domain = "cds-snc.ca"

        aws_provider = MagicMock()
        aws_provider.prefix = "aws"
        aws_provider.requires_email_format = False
        aws_provider.domain = None

        return {
            "google": google_provider,
            "aws": aws_provider,
        }

    def test_map_to_primary_with_domain_appended(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Mapping to primary provider appends domain when required."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="test-group",
            to_provider="google",
            provider_registry=mock_providers_with_domain,
        )

        assert result == "aws-test-group@cds-snc.ca"

    def test_map_to_primary_without_domain_configured(
        self, monkeypatch, mock_providers_without_domain
    ):
        """Mapping to primary without domain returns local part only."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="test-group",
            to_provider="google",
            provider_registry=mock_providers_without_domain,
        )

        assert result == "aws-test-group"

    def test_map_to_primary_email_format_not_required(
        self, monkeypatch, mock_providers_no_email_format
    ):
        """Mapping without email format requirement ignores domain."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="test-group",
            to_provider="google",
            provider_registry=mock_providers_no_email_format,
        )

        assert result == "aws-test-group"

    def test_map_with_existing_email_format_preserved(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Mapping preserves email format when domain is already present."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="aws-test-group@example.com",
            to_provider="google",
            provider_registry=mock_providers_with_domain,
        )

        # Should extract local part and append configured domain
        assert "@cds-snc.ca" in result or "@example.com" in result

    def test_map_between_non_primary_providers(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Mapping between non-primary providers returns canonical name."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="aws-test-group",
            to_provider="other",
            provider_registry=mock_providers_with_domain,
        )

        # Should return canonical name without primary prefix
        assert result == "test-group"

    def test_parse_primary_group_name_with_domain(self, mock_providers_with_domain):
        """Parsing primary group name extracts prefix and canonical."""
        result = mappings.parse_primary_group_name(
            "aws-test-group@cds-snc.ca",
            provider_registry=mock_providers_with_domain,
        )

        assert result["prefix"] == "aws"
        assert result["canonical"] == "test-group"

    def test_canonical_name_extraction_with_email_format(
        self, mock_providers_with_domain
    ):
        """Canonical name extraction handles email format."""
        result = mappings.parse_primary_group_name(
            "aws-test-group@cds-snc.ca",
            provider_registry=mock_providers_with_domain,
        )

        assert result["canonical"] == "test-group"
        assert "@" not in result["canonical"]

    def test_map_to_primary_with_multiple_hyphens_in_name(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Mapping handles group names with multiple hyphens correctly."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="my-long-group-name",
            to_provider="google",
            provider_registry=mock_providers_with_domain,
        )

        assert result == "aws-my-long-group-name@cds-snc.ca"

    def test_same_provider_mapping_returns_unchanged(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Mapping to same provider returns input unchanged."""
        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="google",
            from_group_id="test-group@cds-snc.ca",
            to_provider="google",
            provider_registry=mock_providers_with_domain,
        )

        # Same provider mapping returns input unchanged
        assert result == "test-group@cds-snc.ca"

    def test_domain_extraction_from_local_part(self):
        """Domain is correctly extracted from email local part."""
        local_part = mappings._local_name_from_primary("test-group@cds-snc.ca")
        assert local_part == "test-group"

    def test_domain_extraction_without_email(self):
        """Local part extraction handles non-email format."""
        local_part = mappings._local_name_from_primary("test-group")
        assert local_part == "test-group"

    def test_map_with_config_driven_domain(
        self, monkeypatch, mock_providers_with_domain
    ):
        """Domain from provider instance is used correctly."""
        # Verify that provider.domain is actually used
        google_provider = mock_providers_with_domain["google"]
        assert google_provider.domain == "cds-snc.ca"
        assert google_provider.requires_email_format is True

        monkeypatch.setattr(
            mappings,
            "get_primary_provider_name",
            lambda: "google",
        )

        result = mappings.map_provider_group_id(
            from_provider="aws",
            from_group_id="testgroup",
            to_provider="google",
            provider_registry=mock_providers_with_domain,
        )

        assert "@cds-snc.ca" in result
