"""Behavior tests for runtime-config extensions contracts."""

import json

from packages.access.common.config import InlineJsonConfigLoader


def test_runtime_config_extensions_catalog_is_typed_and_attribute_accessible():
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
    assert result.data.catalog is not None
    assert not isinstance(result.data.catalog, dict)
    assert hasattr(result.data.catalog, "parsers")
    assert "aws" in result.data.catalog.parsers
    assert result.data.catalog.parsers["aws"].known_envs == ["prod", "staging"]
    assert result.data.catalog.platform_display_names["aws"] == "Amazon Web Services"


def test_runtime_config_extensions_invalid_parser_known_envs_shape_fails():
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
                "parsers": {
                    "aws": {
                        "known_envs": "prod",
                    }
                }
            }
        },
    }

    result = InlineJsonConfigLoader().load(json.dumps(payload))

    assert not result.is_success
    assert result.error_code == "CONFIG_INVALID_SHAPE"
