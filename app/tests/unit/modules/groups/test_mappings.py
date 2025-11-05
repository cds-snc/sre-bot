"""Unit tests for groups module provider-aware ID mapping functions.

Tests cover:
- _local_name_from_primary() - Extract local name from primary identifier
- parse_primary_group_name() - Parse primary group name to extract prefix and canonical name
- map_provider_group_id() - Map group IDs between different providers
- primary_group_to_canonical() - Convert primary group name to canonical form
- canonical_to_primary_group() - Convert canonical name to primary group format
- _extract_prefixes_from_registry() - Extract prefix mapping from provider registry
- map_secondary_to_primary_group() - Map from secondary provider to primary
- map_primary_to_secondary_group() - Map from primary provider to secondary

All tests use pure functions with no external I/O dependencies.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from modules.groups import mappings as gm


@pytest.mark.unit
class TestLocalNameFromPrimary:
    """Tests for _local_name_from_primary() helper function."""

    def test_extracts_email_local_part(self):
        """_local_name_from_primary extracts local part from email addresses."""
        assert gm._local_name_from_primary("bob@example.com") == "bob"
        assert gm._local_name_from_primary("alice.smith@company.org") == "alice.smith"
        assert gm._local_name_from_primary("user+tag@domain.co.uk") == "user+tag"

    def test_returns_empty_string_for_empty_input(self):
        """_local_name_from_primary returns empty string for empty input."""
        assert gm._local_name_from_primary("") == ""

    def test_returns_name_as_is_when_no_email_format(self):
        """_local_name_from_primary returns name unchanged when not an email."""
        assert gm._local_name_from_primary("my-group") == "my-group"
        assert gm._local_name_from_primary("prefix-name") == "prefix-name"
        assert gm._local_name_from_primary("GroupName") == "GroupName"

    def test_handles_multiple_at_signs(self):
        """_local_name_from_primary splits on first @ only."""
        assert gm._local_name_from_primary("user@domain@example.com") == "user"


@pytest.mark.unit
class TestEnsureProvidersActivated:
    """Tests for _ensure_providers_activated() function."""

    def test_returns_provided_registry_when_supplied(self):
        """_ensure_providers_activated returns provided registry directly."""
        provs = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        result = gm._ensure_providers_activated(provs)
        assert isinstance(result, dict)
        assert "aws" in result
        assert "google" in result
        assert result["aws"].prefix == "a"

    def test_raises_runtime_error_when_registry_empty(self):
        """_ensure_providers_activated raises RuntimeError when registry is empty."""
        with pytest.raises(RuntimeError):
            gm._ensure_providers_activated({})

    def test_raises_runtime_error_when_registry_none_and_no_active(self):
        """_ensure_providers_activated raises when no active providers found."""
        with patch("modules.groups.mappings.get_active_providers") as mock_get:
            mock_get.return_value = {}
            with pytest.raises(RuntimeError):
                gm._ensure_providers_activated(None)

    def test_uses_active_providers_when_registry_not_provided(self):
        """_ensure_providers_activated fetches active providers when registry is None."""
        with patch("modules.groups.mappings.get_active_providers") as mock_get:
            expected = {"aws": SimpleNamespace(prefix="a")}
            mock_get.return_value = expected
            result = gm._ensure_providers_activated(None)
            assert result == expected


@pytest.mark.unit
class TestParsePrimaryGroupName:
    """Tests for parse_primary_group_name() function."""

    @patch("modules.groups.mappings.get_active_providers")
    def test_parses_colon_separator(self, mock_get_active):
        """parse_primary_group_name handles colon separator."""
        mock_get_active.return_value = {"p": SimpleNamespace(prefix="p")}
        result = gm.parse_primary_group_name("p:foo")
        assert result["prefix"] == "p"
        assert result["canonical"] == "foo"

    @patch("modules.groups.mappings.get_active_providers")
    def test_parses_slash_separator(self, mock_get_active):
        """parse_primary_group_name handles slash separator."""
        mock_get_active.return_value = {"p": SimpleNamespace(prefix="p")}
        result = gm.parse_primary_group_name("p/foo")
        assert result["prefix"] == "p"
        assert result["canonical"] == "foo"

    @patch("modules.groups.mappings.get_active_providers")
    def test_parses_dash_separator(self, mock_get_active):
        """parse_primary_group_name handles dash separator."""
        mock_get_active.return_value = {"p": SimpleNamespace(prefix="p")}
        result = gm.parse_primary_group_name("p-foo")
        assert result["prefix"] == "p"
        assert result["canonical"] == "foo"

    @patch("modules.groups.mappings.get_active_providers")
    def test_prefers_longest_prefix_match(self, mock_get_active):
        """parse_primary_group_name prefers longest matching prefix."""
        mock_get_active.return_value = {
            "a": SimpleNamespace(prefix="a"),
            "ab": SimpleNamespace(prefix="ab"),
        }
        result = gm.parse_primary_group_name("ab:my")
        assert result["prefix"] == "ab"
        assert result["canonical"] == "my"

    @patch("modules.groups.mappings.get_active_providers")
    def test_no_prefix_match_returns_none_prefix(self, mock_get_active):
        """parse_primary_group_name returns None prefix when no match found."""
        mock_get_active.return_value = {"p": SimpleNamespace(prefix="p")}
        result = gm.parse_primary_group_name("other-name")
        assert result["prefix"] is None
        assert result["canonical"] == "other-name"

    def test_raises_on_empty_input(self):
        """parse_primary_group_name raises ValueError on empty input."""
        with pytest.raises(ValueError):
            gm.parse_primary_group_name("")

    def test_raises_on_whitespace_only_input(self):
        """parse_primary_group_name raises ValueError on whitespace-only input."""
        with pytest.raises(ValueError):
            gm.parse_primary_group_name("   ")

    def test_extracts_email_local_part(self):
        """parse_primary_group_name extracts local part from email."""
        provs = {"g": SimpleNamespace(prefix="g")}
        result = gm.parse_primary_group_name(
            "g:user@example.com", provider_registry=provs
        )
        assert result["prefix"] == "g"
        assert result["canonical"] == "user"

    def test_uses_provider_name_when_prefix_attribute_missing(self):
        """parse_primary_group_name uses provider name when prefix attribute not set."""
        provs = {
            "aws": SimpleNamespace(),  # No prefix attribute
            "google": SimpleNamespace(prefix="g"),
        }
        result = gm.parse_primary_group_name("aws-my-group", provider_registry=provs)
        assert result["prefix"] == "aws"
        assert result["canonical"] == "my-group"

    def test_handles_provider_with_empty_string_prefix(self):
        """parse_primary_group_name handles provider with empty string prefix."""
        provs = {
            "aws": SimpleNamespace(prefix=""),
            "google": SimpleNamespace(prefix="g"),
        }
        result = gm.parse_primary_group_name("aws-my", provider_registry=provs)
        assert result["prefix"] == "aws"
        assert result["canonical"] == "my"


@pytest.mark.unit
class TestMapProviderGroupId:
    """Tests for map_provider_group_id() function."""

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_same_provider_returns_same_id(self, mock_get_active, mock_get_primary):
        """map_provider_group_id returns same ID when source and target are same."""
        mock_get_active.return_value = {"a": SimpleNamespace(prefix="a", primary=True)}
        mock_get_primary.return_value = "a"
        result = gm.map_provider_group_id("a", "grp", "a")
        assert result == "grp"

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_maps_from_secondary_to_primary_with_prefix(
        self, mock_get_active, mock_get_primary
    ):
        """map_provider_group_id adds source prefix when mapping to primary."""
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True, prefix="g"),
            "aws": SimpleNamespace(prefix="a"),
        }
        mock_get_primary.return_value = "google"
        result = gm.map_provider_group_id("aws", "my-group", "google")
        assert result == "a-my-group"

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_maps_from_primary_to_secondary_extracts_canonical(
        self, mock_get_active, mock_get_primary
    ):
        """map_provider_group_id extracts canonical when mapping from primary."""
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True, prefix="g"),
            "aws": SimpleNamespace(prefix="a"),
        }
        mock_get_primary.return_value = "google"
        result = gm.map_provider_group_id("google", "g-my-group", "aws")
        assert result == "my-group"

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_uses_provider_name_as_prefix_when_prefix_attr_missing(
        self, mock_get_active, mock_get_primary
    ):
        """map_provider_group_id uses provider name when prefix not configured."""
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True),  # No prefix attribute
            "aws": SimpleNamespace(),  # No prefix attribute
        }
        mock_get_primary.return_value = "google"
        result = gm.map_provider_group_id("aws", "my-group", "google")
        assert result == "aws-my-group"

    def test_raises_value_error_on_empty_inputs(self):
        """map_provider_group_id raises ValueError on empty inputs."""
        provs = {"p": SimpleNamespace(primary=True, prefix="p")}
        with pytest.raises(ValueError):
            gm.map_provider_group_id("", "", "", provider_registry=provs)

    def test_raises_on_unknown_source_provider(self):
        """map_provider_group_id raises ValueError for unknown source provider."""
        provs = {"google": SimpleNamespace(primary=True, prefix="g")}
        with pytest.raises(ValueError):
            gm.map_provider_group_id(
                "aws", "my-group", "google", provider_registry=provs
            )

    def test_raises_on_unknown_target_provider(self):
        """map_provider_group_id raises ValueError for unknown target provider."""
        provs = {"aws": SimpleNamespace(prefix="a")}
        with pytest.raises(ValueError):
            gm.map_provider_group_id(
                "aws", "my-group", "google", provider_registry=provs
            )

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_raises_when_providers_not_activated(
        self, mock_get_active, mock_get_primary
    ):
        """map_provider_group_id raises when no providers are active."""
        mock_get_active.return_value = {}
        with pytest.raises(RuntimeError):
            gm.map_provider_group_id("aws", "group", "google")


@pytest.mark.unit
class TestPrimaryGroupToCanonical:
    """Tests for primary_group_to_canonical() function."""

    def test_strips_longest_matching_prefix(self):
        """primary_group_to_canonical strips longest matching prefix."""
        result = gm.primary_group_to_canonical("ab-my", prefixes=["a", "ab"])
        assert result == "my"

    def test_strips_with_single_prefix(self):
        """primary_group_to_canonical strips single prefix."""
        result = gm.primary_group_to_canonical("a-my-group", prefixes=["a"])
        assert result == "my-group"

    def test_returns_unchanged_when_no_prefix_match(self):
        """primary_group_to_canonical returns name unchanged when no prefix matches."""
        result = gm.primary_group_to_canonical("my-group", prefixes=["a", "b"])
        assert result == "my-group"

    def test_extracts_email_local_part(self):
        """primary_group_to_canonical extracts local part from email."""
        result = gm.primary_group_to_canonical("user@example.com", prefixes=None)
        assert result == "user"

    def test_returns_unchanged_for_no_prefixes_no_email(self):
        """primary_group_to_canonical returns unchanged when prefixes None and no email."""
        result = gm.primary_group_to_canonical("foo-bar", prefixes=None)
        assert result == "foo-bar"

    def test_returns_empty_string_for_empty_input(self):
        """primary_group_to_canonical returns empty string for empty input."""
        result = gm.primary_group_to_canonical("", prefixes=["a"])
        assert result == ""

    def test_prefers_longest_prefix_over_shorter(self):
        """primary_group_to_canonical prefers longest prefix."""
        result = gm.primary_group_to_canonical("prefix-name", prefixes=["p", "prefix"])
        assert result == "name"

    def test_handles_prefix_with_dash_separator(self):
        """primary_group_to_canonical handles dash-separated prefixes."""
        result = gm.primary_group_to_canonical("aws-us-east-1", prefixes=["aws"])
        assert result == "us-east-1"


@pytest.mark.unit
class TestCanonicalToPrimaryGroup:
    """Tests for canonical_to_primary_group() function."""

    def test_prepends_prefix_with_dash(self):
        """canonical_to_primary_group prepends prefix with dash separator."""
        result = gm.canonical_to_primary_group("my-group", "p")
        assert result == "p-my-group"

    def test_returns_empty_for_empty_canonical(self):
        """canonical_to_primary_group returns empty string for empty canonical name."""
        result = gm.canonical_to_primary_group("", "p")
        assert result == ""

    def test_returns_canonical_when_prefix_none(self):
        """canonical_to_primary_group returns canonical unchanged when prefix is None."""
        result = gm.canonical_to_primary_group("my-group", None)
        assert result == "my-group"

    def test_handles_complex_canonical_names(self):
        """canonical_to_primary_group handles complex names with multiple separators."""
        result = gm.canonical_to_primary_group("prod-us-east-1-api", "aws")
        assert result == "aws-prod-us-east-1-api"


@pytest.mark.unit
class TestExtractPrefixesFromRegistry:
    """Tests for _extract_prefixes_from_registry() helper function."""

    def test_extracts_prefixes_from_dict_configs(self):
        """_extract_prefixes_from_registry extracts prefix from dict configurations."""
        registry = {
            "a": {"prefix": "x"},
            "b": {"prefix": "y"},
        }
        provider_to_prefix, prefixes = gm._extract_prefixes_from_registry(registry)
        assert provider_to_prefix["a"] == "x"
        assert provider_to_prefix["b"] == "y"
        assert "x" in prefixes
        assert "y" in prefixes

    def test_uses_provider_name_when_prefix_missing(self):
        """_extract_prefixes_from_registry uses provider name when prefix not in config."""
        registry = {
            "aws": {},  # No prefix key
            "google": {"prefix": "g"},
        }
        provider_to_prefix, prefixes = gm._extract_prefixes_from_registry(registry)
        assert provider_to_prefix["aws"] == "aws"
        assert provider_to_prefix["google"] == "g"

    def test_handles_non_dict_configs(self):
        """_extract_prefixes_from_registry handles non-dict config values."""
        registry = {
            "aws": "raw-string",  # Not a dict
            "google": {"prefix": "g"},
        }
        provider_to_prefix, prefixes = gm._extract_prefixes_from_registry(registry)
        assert provider_to_prefix["aws"] == "aws"
        assert provider_to_prefix["google"] == "g"

    def test_builds_prefix_list(self):
        """_extract_prefixes_from_registry builds list of unique prefixes."""
        registry = {
            "a": {"prefix": "x"},
            "b": "notadict",
            "c": {},
        }
        provider_to_prefix, prefixes = gm._extract_prefixes_from_registry(registry)
        assert "x" in prefixes
        assert "b" in prefixes
        assert "c" in prefixes


@pytest.mark.unit
class TestMapSecondaryToPrimaryGroup:
    """Tests for map_secondary_to_primary_group() function."""

    @patch("modules.groups.mappings.map_provider_group_id", return_value="a-my-group")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_maps_secondary_to_primary_successfully(self, mock_get_primary, mock_map):
        """map_secondary_to_primary_group maps from secondary to primary provider."""
        result = gm.map_secondary_to_primary_group("aws", "my-group")
        assert result == "a-my-group"
        mock_map.assert_called_once_with(
            from_provider="aws", from_group_id="my-group", to_provider="google"
        )

    @patch(
        "modules.groups.mappings.map_provider_group_id", side_effect=Exception("error")
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_raises_on_mapping_failure(self, mock_get_primary, mock_map):
        """map_secondary_to_primary_group raises ValueError on mapping failure."""
        with pytest.raises(ValueError):
            gm.map_secondary_to_primary_group("aws", "my-group")

    @patch(
        "modules.groups.mappings.map_provider_group_id",
        side_effect=RuntimeError("Service error"),
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_error_message_includes_context(self, mock_get_primary, mock_map):
        """map_secondary_to_primary_group error message includes provider info."""
        with pytest.raises(ValueError) as exc_info:
            gm.map_secondary_to_primary_group("aws", "my-group")
        assert "Cannot map" in str(exc_info.value)


@pytest.mark.unit
class TestMapPrimaryToSecondaryGroup:
    """Tests for map_primary_to_secondary_group() function."""

    @patch("modules.groups.mappings.map_provider_group_id", return_value="my-group")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_maps_primary_to_secondary_successfully(self, mock_get_primary, mock_map):
        """map_primary_to_secondary_group maps from primary to secondary provider."""
        result = gm.map_primary_to_secondary_group("g-my-group", "aws")
        assert result == "my-group"
        mock_map.assert_called_once_with(
            from_provider="google", from_group_id="g-my-group", to_provider="aws"
        )

    @patch(
        "modules.groups.mappings.map_provider_group_id", side_effect=Exception("error")
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_raises_on_mapping_failure(self, mock_get_primary, mock_map):
        """map_primary_to_secondary_group raises ValueError on mapping failure."""
        with pytest.raises(ValueError):
            gm.map_primary_to_secondary_group("g-my-group", "aws")

    @patch(
        "modules.groups.mappings.map_provider_group_id",
        side_effect=RuntimeError("Service error"),
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_error_message_includes_context(self, mock_get_primary, mock_map):
        """map_primary_to_secondary_group error message includes provider info."""
        with pytest.raises(ValueError) as exc_info:
            gm.map_primary_to_secondary_group("g-my-group", "aws")
        assert "Cannot map" in str(exc_info.value)
