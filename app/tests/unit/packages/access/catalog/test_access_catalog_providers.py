"""Behavior tests for access catalog provider wiring."""

import json
from unittest.mock import MagicMock

import pytest

from packages.access.catalog import providers
from packages.access.common.config import InlineJsonConfigLoader


def _runtime_config_from_payload() -> object:
    payload = {
        "dir_prefix": "sg",
        "dir_separator": "-",
        "platforms": {
            "aws": {
                "authn_token": "authn",
                "authn_removal_mode": "delete",
                "mode_overrides": {},
            }
        },
        "extensions": {
            "catalog": {
                "parsers": {"aws": {"known_envs": ["prod", "staging"]}},
                "platform_display_names": {"aws": "Amazon Web Services"},
            }
        },
    }
    result = InlineJsonConfigLoader().load(json.dumps(payload))
    assert result.is_success
    assert result.data is not None
    return result.data


@pytest.mark.unit
def test_build_parser_map_applies_known_envs_from_runtime_extensions(monkeypatch):
    providers._build_parser_map.cache_clear()

    monkeypatch.setattr(
        providers,
        "get_access_runtime_config",
        _runtime_config_from_payload,
    )

    parsers = providers._build_parser_map()
    parsed = parsers["aws"].parse("billing-prod-admin")

    assert parsed.parsed is True
    assert parsed.env == "prod"

    providers._build_parser_map.cache_clear()


@pytest.mark.unit
def test_get_catalog_service_applies_display_names_from_runtime_extensions(monkeypatch):
    providers._build_parser_map.cache_clear()
    providers.get_catalog_service.cache_clear()

    monkeypatch.setattr(
        providers,
        "get_access_runtime_config",
        _runtime_config_from_payload,
    )
    monkeypatch.setattr(providers, "get_directory_provider", lambda: MagicMock())

    result = providers.get_catalog_service().list_platforms()

    assert result.is_success
    assert result.data is not None
    assert result.data[0].display_name == "Amazon Web Services"

    providers._build_parser_map.cache_clear()
    providers.get_catalog_service.cache_clear()
