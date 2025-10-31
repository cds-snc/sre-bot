# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,protected-access
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from modules.groups import mappings as gm
from modules.groups import service as gs
from modules.groups.models import NormalizedMember


class MapNormalizedGroupsListToProvidersTests:

    @patch("modules.groups.mappings.get_active_providers")
    def test_map_normalized_groups_to_providers_handles_dict_and_namespace_and_unknown(
        self,
        mock_get_active,
    ):
        # no need for active providers here
        mock_get_active.return_value = {"google": SimpleNamespace(prefix="g")}

        ns = SimpleNamespace(id="h", provider="google")
        groups = [{"id": "g", "provider": "aws"}, ns, {"id": "no_provider"}]
        res = gm.map_normalized_groups_to_providers(groups)
        assert "aws" in res and isinstance(res["aws"], list)
        assert "google" in res and isinstance(res["google"], list)
        assert "unknown" in res and isinstance(res["unknown"], list)

    def test_map_normalized_groups_to_providers_object_and_dict(self):
        class G:
            def __init__(self, provider=None, id=None):
                self.provider = provider
                self.id = id

        d = {"provider": "a", "id": "1"}
        o = G(provider="b", id="2")
        res = gm.map_normalized_groups_to_providers([d, o])
        assert "a" in res and "b" in res
        assert res["a"][0]["id"] == "1"
        assert getattr(res["b"][0], "id") == "2"

    def test_map_normalized_groups_to_providers_updates_provider_for_known_prefix(
        self,
    ):
        # provider registry with prefixes
        provs = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }

        # dict-style group that should be associated to aws via 'a-' prefix
        groups = [{"id": "a-my", "provider": "unknown"}]

        res = gm.map_normalized_groups_to_providers(groups, provider_registry=provs)
        # provider should be updated to 'aws'
        assert "aws" in res
        assert any(
            (isinstance(g, dict) and g.get("provider") == "aws") for g in res["aws"]
        )

    def test_map_normalized_groups_to_providers_handles_immutable_object(
        self,
    ):
        class ReadOnlyGroup:
            __slots__ = ("id", "provider")

            def __init__(self, id, provider=None):
                self.id = id
                self.provider = provider

        provs = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        # object that won't allow setattr because of slots is still mutable for attributes, but
        # simulate an object that raises on setattr by making provider a property

        class FrozenGroup:
            def __init__(self, id):
                self._id = id

            @property
            def id(self):
                return self._id

            @property
            def provider(self):
                return None

        fg = FrozenGroup("a-my")
        groups = [fg]

        # Should not raise when trying to set provider on an immutable object
        res = gm.map_normalized_groups_to_providers(groups, provider_registry=provs)
        # group should still appear under some provider key (unknown if not writable)
        assert any(len(v) > 0 for v in res.values())

    def test_map_normalized_groups_to_providers_longest_prefix_win(
        self,
    ):
        provs = {
            "a": SimpleNamespace(prefix="a"),
            "ab": SimpleNamespace(prefix="ab"),
        }
        groups = [{"id": "ab-my", "provider": "unknown"}]
        res = gm.map_normalized_groups_to_providers(groups, provider_registry=provs)
        # group should be associated with provider 'ab'
        assert "ab" in res
        assert any(isinstance(g, dict) and g.get("provider") == "ab" for g in res["ab"])

    def test_map_normalized_groups_to_providers_immutable_group(
        self,
    ):
        # Immutable-like object: setting attributes will raise
        class Immutable:
            def __init__(self, id):
                object.__setattr__(self, "id", id)

            def __setattr__(self, name, value):
                raise TypeError("immutable")

        registry = {"aws": {"prefix": "aws"}}
        g = Immutable("aws-my-group")
        res = gm.map_normalized_groups_to_providers([g], provider_registry=registry)
        # Mutation should fail and the group falls back to 'unknown'
        assert "unknown" in res
        assert res["unknown"][0] is g

    @patch("modules.groups.mappings.get_active_providers")
    def test_map_normalized_groups_to_providers_uses_active_providers(
        self, mock_get_active
    ):
        mock_get_active.return_value = {
            "aws": SimpleNamespace(prefix="a"),
            "google": SimpleNamespace(prefix="g"),
        }
        groups = [{"id": "a-special", "provider": None}]
        res = gm.map_normalized_groups_to_providers(groups)
        assert "aws" in res
        assert any(
            isinstance(g, dict) and g.get("provider") == "aws" for g in res["aws"]
        )


class NormalizeMemberForProviderTests:
    def test_normalize_member_for_provider_valid_and_invalid(self):
        # valid
        nm = gs.normalize_member_for_provider("a@b.com", "aws")
        assert nm.email == "a@b.com"

        # invalid
        with pytest.raises(ValueError):
            gs.normalize_member_for_provider("no-at", "aws")

    def test_normalize_member_for_provider_invalid_and_valid(self):
        with pytest.raises(ValueError):
            gs.normalize_member_for_provider("noats", "aws")

        nm = gs.normalize_member_for_provider("a@b", "aws")
        assert isinstance(nm, NormalizedMember)
        assert nm.email == "a@b"
        assert nm.id is None
