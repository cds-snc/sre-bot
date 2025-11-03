# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,protected-access
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from modules.groups import mappings as gm

# NormalizedMember import removed — not used in these tests (fixes flake8 F401)

pytestmark = pytest.mark.legacy


class LocalNameFromPrimaryTests:
    def test_local_name_from_primary_handles_email_local_part_and_empty(self):
        assert gm._local_name_from_primary("bob@example.com") == "bob"
        assert gm._local_name_from_primary("") == ""


class EnsureProvidersActivatedTests:

    @patch("modules.groups.mappings.get_active_providers")
    def test_ensure_providers_activated_raises_when_no_active(self, mock_get_active):
        mock_get_active.return_value = {}
        with pytest.raises(RuntimeError):
            gm._ensure_providers_activated()

    def test_ensure_providers_activated_uses_passed_registry(self):
        provs = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        # passing provider_registry should be returned as dict
        res = gm._ensure_providers_activated(provs)
        assert isinstance(res, dict)
        assert "aws" in res and "google" in res

    @patch("modules.groups.mappings.get_active_providers")
    def test_ensure_providers_activated_raises_on_empty_active(self, mock_get_active):
        mock_get_active.return_value = {}
        with pytest.raises(RuntimeError):
            # call a function that uses _ensure_providers_activated indirectly
            gm.parse_primary_group_name("some-group")

    def test_map_provider_group_id_raises_when_providers_not_activated(self):
        # passing an empty provider_registry should raise RuntimeError via _ensure_providers_activated
        with pytest.raises(RuntimeError):
            gm.map_provider_group_id("a", "b", "c", provider_registry={})


class ParsePrimaryGroupNameTests:
    @patch("modules.groups.mappings.get_active_providers")
    def test_parse_primary_group_name_matches_colon_and_slash_and_dash(
        self, mock_get_active
    ):
        # providers with prefix 'p'
        mock_get_active.return_value = {
            "p": SimpleNamespace(prefix="p"),
        }

        for sep in (":", "/", "-"):
            name = f"p{sep}foo"
            res = gm.parse_primary_group_name(name)
            assert res["prefix"] == "p"
            assert res["canonical"] == "foo"

    @patch("modules.groups.mappings.get_active_providers")
    def test_parse_primary_group_name_prefers_longest_prefix(self, mock_get_active):
        # overlapping prefixes: 'a' and 'ab' -> 'ab' should win
        mock_get_active.return_value = {
            "a": SimpleNamespace(prefix="a"),
            "ab": SimpleNamespace(prefix="ab"),
        }

        res = gm.parse_primary_group_name("ab:my")
        assert res["prefix"] == "ab"
        assert res["canonical"] == "my"

    def test_parse_primary_group_name_raises_on_empty_input(self):
        with pytest.raises(ValueError):
            gm.parse_primary_group_name("")

    def test_parse_primary_group_name_when_provider_prefix_is_empty_string(self):
        provs = {
            "aws": SimpleNamespace(prefix=""),
            "google": SimpleNamespace(prefix="g"),
        }
        res = gm.parse_primary_group_name("aws-my", provider_registry=provs)
        assert res["prefix"] == "aws"
        assert res["canonical"] == "my"

    def test_parse_primary_group_name_separators(self):
        registry = {"p": SimpleNamespace(prefix="px")}
        for sep in (":", "/", "-"):
            name = f"px{sep}canon"
            parsed = gm.parse_primary_group_name(name, provider_registry=registry)
            assert parsed["prefix"] == "px"
            assert parsed["canonical"] == "canon"

    @patch("modules.groups.mappings.get_active_providers")
    def test_parse_primary_group_name_handles_email_local_part(self, mock_get_active):
        mock_get_active.return_value = {"g": SimpleNamespace(prefix="g")}
        res = gm.parse_primary_group_name("g:user@example.com")
        assert res["prefix"] == "g"
        assert res["canonical"] == "user"


class MapProviderGroupIDTests:
    """Tests for the map_provider_group_id function."""

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_same_provider_returns_same(self, mock_get_active, mock_get_primary):
        mock_get_active.return_value = {"a": SimpleNamespace(prefix="a", primary=True)}
        mock_get_primary.return_value = "a"
        assert gm.map_provider_group_id("a", "grp", "a") == "grp"

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_map_to_primary_with_prefix(self, mock_get_active, mock_get_primary):
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True, prefix="g"),
            "aws": SimpleNamespace(prefix="a"),
        }
        mock_get_primary.return_value = "google"

        # mapping from aws canonical to primary -> should add aws prefix
        res = gm.map_provider_group_id(
            from_provider="aws", from_group_id="my-group", to_provider="google"
        )
        assert res == "a-my-group"

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_map_to_primary_without_prefix_configured(
        self, mock_get_active, mock_get_primary
    ):
        # When primary provider does not declare a prefix attribute, mapping to primary
        # composes the primary-style name using the source provider's effective prefix
        # (which defaults to the source provider name when not set). Here aws has a
        # configured prefix so we expect that to be used.
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True),
            "aws": SimpleNamespace(prefix="a"),
        }
        mock_get_primary.return_value = "google"

        res = gm.map_provider_group_id(
            from_provider="aws", from_group_id="my-group", to_provider="google"
        )
        assert res == "a-my-group"

    def test_map_provider_group_id_raises_when_source_provider_unknown(self):
        # provider registry contains only 'google' as active
        provs = {"google": SimpleNamespace(primary=True, prefix="g")}
        with pytest.raises(ValueError):
            gm.map_provider_group_id(
                "aws", "my-group", "google", provider_registry=provs
            )

    @patch("modules.groups.mappings.get_primary_provider_name")
    @patch("modules.groups.mappings.get_active_providers")
    def test_map_between_non_primary_and_non_primary(
        self, mock_get_active, mock_get_primary
    ):
        mock_get_active.return_value = {
            "google": SimpleNamespace(primary=True, prefix="g"),
            "aws": SimpleNamespace(prefix="a"),
            "okta": SimpleNamespace(prefix="okta"),
        }
        mock_get_primary.return_value = "google"

        # map from google primary-style name to aws -> should return canonical
        res = gm.map_provider_group_id(
            from_provider="google", from_group_id="g-my-group", to_provider="aws"
        )
        assert res == "my-group"

    def test_invalid_inputs_raises(self):
        try:
            gm.map_provider_group_id("", "", "")
            raised = False
        except ValueError:
            raised = True
        assert raised

    def test_map_provider_group_id_unknown_source_raises(self):
        registry = {"primary": SimpleNamespace(prefix="p")}
        with patch(
            "modules.groups.mappings.get_primary_provider_name", return_value="primary"
        ):
            with pytest.raises(ValueError) as exc:
                gm.map_provider_group_id(
                    from_provider="nope",
                    from_group_id="grp",
                    to_provider="primary",
                    provider_registry=registry,
                )
            assert "Unknown source provider" in str(exc.value)

    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_map_provider_group_id_uses_provider_name_when_no_prefix_attr(
        self, mock_get_primary
    ):
        provs = {"aws": SimpleNamespace(), "google": SimpleNamespace(primary=True)}
        res = gm.map_provider_group_id("aws", "my", "google", provider_registry=provs)
        assert res == "aws-my"


class PrimaryGroupToCanonicalTests:

    def test_primary_group_to_canonical_strips_longest_prefix_and_handles_email(self):
        # strips 'ab-' when prefixes provided
        assert gm.primary_group_to_canonical("ab-my", prefixes=["a", "ab"]) == "my"
        # email local part
        assert (
            gm.primary_group_to_canonical("user@example.com", prefixes=None) == "user"
        )

    def test_primary_group_to_canonical_no_prefixes_returns_name(self):
        assert gm.primary_group_to_canonical("foo-bar", prefixes=None) == "foo-bar"

    def test_primary_group_to_canonical_empty_returns_empty(self):
        assert gm.primary_group_to_canonical("", prefixes=["a"]) == ""


class CanonicalToPrimaryGroupTests:
    def test_canonical_to_primary_group_with_and_without_prefix(self):
        assert gm.canonical_to_primary_group("my", "p") == "p-my"
        assert gm.canonical_to_primary_group("", "p") == ""

    def test_primary_group_to_canonical_and_canonical_to_primary(self):
        assert gm.primary_group_to_canonical("x", prefixes=["y"]) == "x"
        assert gm.canonical_to_primary_group("name", "p") == "p-name"
        assert gm.canonical_to_primary_group("name", None) == "name"


class ExtractPrefixesFromRegistryTests:
    def test_extract_prefixes_from_registry_with_mixed_cfg_types(self):
        registry = {
            "a": {"prefix": "x"},
            "b": "notamap",
            "c": {},
        }
        provider_to_prefix, prefixes = gm._extract_prefixes_from_registry(registry)
        assert provider_to_prefix["a"] == "x"
        assert provider_to_prefix["b"] == "b"
        assert provider_to_prefix["c"] == "c"
        assert set(prefixes) >= {"x", "b", "c"}

    def test_extract_prefixes_from_registry_with_non_mapping_cfg(self):
        registry = {"aws": "raw", "g": {"prefix": "gp"}}
        prov_to_pref, prefixes = gm._extract_prefixes_from_registry(registry)
        assert prov_to_pref["aws"] == "aws"
        assert prov_to_pref["g"] == "gp"
        assert set(prefixes) == {"aws", "gp"}


class MapSecondaryPrimaryGroupTests:
    """Tests for mapping between secondary and primary group IDs."""

    @patch("modules.groups.service.map_provider_group_id", return_value="a-my-group")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_map_secondary_to_primary_group_success(self, mock_get_primary, mock_map):
        res = gm.map_secondary_to_primary_group("aws", "my-group")
        assert res == "a-my-group"
        mock_map.assert_called_once_with(
            from_provider="aws", from_group_id="my-group", to_provider="google"
        )

    @patch(
        "modules.groups.service.map_provider_group_id", side_effect=Exception("boom")
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_map_secondary_to_primary_group_raises_on_failure(
        self, mock_get_primary, mock_map
    ):
        with pytest.raises(ValueError):
            gm.map_secondary_to_primary_group("aws", "my-group")

    @patch("modules.groups.service.map_provider_group_id", return_value="id")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="primary")
    def test_map_secondary_to_primary_group_error_path(
        self, mock_get_primary, mock_map
    ):
        with pytest.raises(ValueError) as exc:
            gm.map_secondary_to_primary_group("aws", "id")
            assert "Cannot map" in str(exc.value)


class MapPrimaryToSecondaryGroupTests:

    @patch("modules.groups.service.map_provider_group_id", return_value="my-group")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_map_primary_to_secondary_group_success(self, mock_get_primary, mock_map):
        res = gm.map_primary_to_secondary_group("g-my-group", "aws")
        assert res == "my-group"
        mock_map.assert_called_once_with(
            from_provider="google", from_group_id="g-my-group", to_provider="aws"
        )

    @patch(
        "modules.groups.service.map_provider_group_id", side_effect=Exception("boom")
    )
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="google")
    def test_map_primary_to_secondary_group_raises_on_failure(
        self, mock_get_primary, mock_map
    ):
        with pytest.raises(ValueError):
            gm.map_primary_to_secondary_group("g-my-group", "aws")

    @patch("modules.groups.service.map_provider_group_id", return_value="id")
    @patch("modules.groups.mappings.get_primary_provider_name", return_value="primary")
    def test_map_primary_to_secondary_group_error_path(
        self, mock_get_primary, mock_map
    ):
        with pytest.raises(ValueError) as exc:
            gm.map_primary_to_secondary_group("p-id", "aws")
        assert "Cannot map" in str(exc.value)
